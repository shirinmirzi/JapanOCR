import contextlib
import logging
import os
import re
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from config.database import get_db_connection
from middleware.entra_auth import get_current_user
from services.azure_storage_client import azure_storage_client
from services.docwise_client import analyze_document, extract_invoice_data
from services.file_metadata_client import (
    create_invoice,
    get_invoice_by_id,
    get_invoices_by_job,
    get_invoices_paged,
    soft_delete_invoice,
)
from services.jobs import create_job, increment_processed, set_job_results, set_job_status
from services.logging_client import log_processing_start, update_log_entry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/invoices")

_DO_NOT_SEND_FOLDER = "DoNotSend"

_MASTER_TABLE = {
    "daily": "daily_invoice_master",
    "monthly": "monthly_invoice_master",
}


def _build_upload_folder() -> str:
    now = datetime.now(timezone.utc)
    return f"uploads/{now.strftime('%Y/%m/%d')}"


def _build_execution_folder() -> str:
    """Returns e.g. '20250430_143022' using current UTC date and time."""
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y%m%d')}_{now.strftime('%H%M%S')}"


def _build_renamed_filename(customer_code: str, invoice_number: str, invoice_date: str) -> str:
    """Build renamed filename: CustomerCode_InvoiceNumber_YYYYMMDD納品書兼請求書.pdf"""
    if invoice_date and invoice_date != "N/A":
        date_str = invoice_date.replace("/", "").replace("-", "")
    else:
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{customer_code}_{invoice_number}_{date_str}納品書兼請求書.pdf"


def _lookup_master(customer_code: str, invoice_type: str) -> tuple[str, bool]:
    """Look up customer_code in the master table for the given invoice_type.

    Returns (effective_code, is_do_not_send):
    - effective_code: destination_cd from master when matched and numeric,
      otherwise the original customer_code.
    - is_do_not_send: True when the master entry's destination_cd is
      non-numeric (e.g. 送付無し, 破棄), indicating the file must be routed
      to the DoNotSend folder.

    If no matching row exists the original customer_code is returned as-is
    and is_do_not_send is False.
    """
    table_name = _MASTER_TABLE.get(invoice_type)
    if not table_name:
        return customer_code, False

    table_ident = sql.Identifier(table_name)
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    sql.SQL("SELECT destination_cd FROM {} WHERE customer_cd = %s LIMIT 1").format(table_ident),
                    (customer_code,),
                )
                row = cur.fetchone()
    except Exception as exc:
        logger.warning("Master lookup failed for customer_code=%s invoice_type=%s: %s", customer_code, invoice_type, exc)
        return customer_code, False

    if row is None:
        return customer_code, False

    destination_cd = (row.get("destination_cd") or "").strip()
    # A destination_cd that is not purely numeric signals a DoNotSend rule
    # (e.g. Japanese words like 送付無し or 破棄).
    if not re.fullmatch(r'\d+', destination_cd):
        return customer_code, True

    return destination_cd, False


async def _process_single_file(
    file: UploadFile,
    user_id: str,
    job_id: str = None,
    invoice_type: str = "daily",
    execution_folder: str = None,
) -> dict:
    content = await file.read()
    filename = file.filename

    if execution_folder is None:
        execution_folder = _build_execution_folder()

    log_id = log_processing_start(
        filename,
        user_id=user_id,
        execution_folder=execution_folder,
        module="invoice",
    )

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        invoice_data = {}
        ocr_error = None
        try:
            with open(tmp_path, "rb") as f:
                raw_response = analyze_document(f, filename, invoice_type=invoice_type)
            invoice_data = extract_invoice_data(raw_response, invoice_type=invoice_type)
        except Exception as e:
            logger.error("OCR failed for %s: %s", filename, e)
            ocr_error = str(e)
        finally:
            with contextlib.suppress(Exception):
                os.unlink(tmp_path)

        # Determine output subfolder and renamed filename (daily only)
        renamed_filename = None
        output_folder = "ProcessedFiles"
        if invoice_type == "daily":
            customer_code = invoice_data.get("customer_code", "N/A")
            invoice_number = invoice_data.get("invoice_number", "N/A")
            invoice_date = invoice_data.get("invoice_date", "N/A")
            if ocr_error or customer_code == "N/A" or invoice_number == "N/A":
                output_folder = "Error"
            else:
                effective_code, is_do_not_send = _lookup_master(customer_code, invoice_type)
                if is_do_not_send:
                    output_folder = _DO_NOT_SEND_FOLDER
                renamed_filename = _build_renamed_filename(
                    effective_code, invoice_number, invoice_date
                )

        dest_name = renamed_filename if renamed_filename else filename
        blob_path = f"executions/{execution_folder}/{output_folder}/{dest_name}"

        blob_url = None
        try:
            blob_url = azure_storage_client.upload_file(content, blob_path)
        except Exception as e:
            logger.warning("Failed to upload %s to Azure: %s", dest_name, e)

        if ocr_error:
            update_log_entry(
                log_id,
                "error",
                error=ocr_error,
                folder_name=output_folder,
            )
            record = create_invoice(
                job_id=job_id,
                filename=filename,
                invoice_data=invoice_data,
                blob_url=blob_url,
                blob_path=blob_path,
                upload_folder=f"executions/{execution_folder}/{output_folder}",
                user_id=user_id,
            )
            return {
                **invoice_data,
                "id": record.get("id"),
                "blob_url": blob_url,
                "filename": filename,
                "renamed_filename": None,
                "output_folder": output_folder,
                "execution_folder": execution_folder,
                "blob_path": blob_path,
                "error": ocr_error,
            }

        # Update log to success BEFORE creating the invoice record so the log
        # always reaches a terminal state even if create_invoice raises.
        update_log_entry(
            log_id,
            "success",
            message="Invoice processed",
            renamed_filename=renamed_filename,
            folder_name=output_folder,
        )
        record = create_invoice(
            job_id=job_id,
            filename=filename,
            invoice_data=invoice_data,
            blob_url=blob_url,
            blob_path=blob_path,
            upload_folder=f"executions/{execution_folder}/{output_folder}",
            user_id=user_id,
        )
        return {
            **invoice_data,
            "id": record.get("id"),
            "blob_url": blob_url,
            "filename": filename,
            "renamed_filename": renamed_filename,
            "output_folder": output_folder,
            "execution_folder": execution_folder,
            "blob_path": blob_path,
        }
    except Exception as e:
        # Ensure the log always reaches a terminal state even when an
        # unexpected exception escapes the normal success/error paths above.
        update_log_entry(log_id, "error", error=f"Processing failed: {e}")
        raise


def _background_bulk_process(job_id: str, files_data: list, user_id: str, invoice_type: str = "daily", execution_folder: str = None):
    if execution_folder is None:
        execution_folder = _build_execution_folder()
    set_job_status(job_id, "processing")
    results = {}
    for item in files_data:
        filename = item["filename"]
        content = item["content"]

        log_id = log_processing_start(
            filename,
            user_id=user_id,
            execution_folder=execution_folder,
            module="invoice",
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        invoice_data = {}
        ocr_error = None
        try:
            with open(tmp_path, "rb") as f:
                raw_response = analyze_document(f, filename, invoice_type=invoice_type)
            invoice_data = extract_invoice_data(raw_response, invoice_type=invoice_type)
        except Exception as e:
            logger.error("Bulk OCR failed for %s: %s", filename, e)
            ocr_error = str(e)
        finally:
            with contextlib.suppress(Exception):
                os.unlink(tmp_path)

        # Determine output subfolder and renamed filename (daily only)
        renamed_filename = None
        output_folder = "ProcessedFiles"
        if invoice_type == "daily":
            customer_code = invoice_data.get("customer_code", "N/A")
            invoice_number = invoice_data.get("invoice_number", "N/A")
            invoice_date = invoice_data.get("invoice_date", "N/A")
            if ocr_error or customer_code == "N/A" or invoice_number == "N/A":
                output_folder = "Error"
            else:
                effective_code, is_do_not_send = _lookup_master(customer_code, invoice_type)
                if is_do_not_send:
                    output_folder = _DO_NOT_SEND_FOLDER
                renamed_filename = _build_renamed_filename(
                    effective_code, invoice_number, invoice_date
                )

        dest_name = renamed_filename if renamed_filename else filename
        blob_path = f"executions/{execution_folder}/{output_folder}/{dest_name}"
        blob_url = None
        try:
            blob_url = azure_storage_client.upload_file(content, blob_path)
        except Exception as e:
            logger.warning("Failed to upload %s to Azure: %s", dest_name, e)

        upload_folder = f"executions/{execution_folder}/{output_folder}"
        if ocr_error:
            create_invoice(
                job_id=job_id,
                filename=filename,
                invoice_data=invoice_data,
                blob_url=blob_url,
                blob_path=blob_path,
                upload_folder=upload_folder,
                user_id=user_id,
            )
            results[filename] = {
                "status": "failed",
                "error": ocr_error,
                "renamed_filename": None,
                "output_folder": output_folder,
            }
            update_log_entry(
                log_id,
                "error",
                error=ocr_error,
                folder_name=output_folder,
            )
        else:
            create_invoice(
                job_id=job_id,
                filename=filename,
                invoice_data=invoice_data,
                blob_url=blob_url,
                blob_path=blob_path,
                upload_folder=upload_folder,
                user_id=user_id,
            )
            results[filename] = {
                "status": "done",
                **invoice_data,
                "renamed_filename": renamed_filename,
                "output_folder": output_folder,
            }
            update_log_entry(
                log_id,
                "success",
                message="Bulk invoice processed",
                renamed_filename=renamed_filename,
                folder_name=output_folder,
            )

        increment_processed(job_id)

    failed = sum(1 for r in results.values() if r.get("status") == "failed")
    final_status = (
        "failed" if failed == len(files_data) else "partial" if failed else "done"
    )
    set_job_status(job_id, final_status)
    set_job_results(job_id, results)


_VALID_INVOICE_TYPES = {"daily", "monthly"}


@router.post("/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    invoice_type: str = Form("daily"),
    user_date: str = Form(None),  # Accepted for backward compatibility but no longer used
    user: dict = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    if invoice_type not in _VALID_INVOICE_TYPES:
        raise HTTPException(status_code=400, detail="invoice_type must be 'daily' or 'monthly'")
    result = await _process_single_file(
        file, user["username"], invoice_type=invoice_type
    )
    return result


@router.post("/bulk-upload")
async def bulk_upload_invoices(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    invoice_type: str = Form("daily"),
    user_date: str = Form(None),  # Accepted for backward compatibility but no longer used
    user: dict = Depends(get_current_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    if invoice_type not in _VALID_INVOICE_TYPES:
        raise HTTPException(status_code=400, detail="invoice_type must be 'daily' or 'monthly'")

    execution_folder = _build_execution_folder()
    filenames = [f.filename for f in files]
    job_id = create_job(filenames=filenames, user_id=user["username"])

    files_data = []
    for f in files:
        content = await f.read()
        files_data.append({"filename": f.filename, "content": content})

    background_tasks.add_task(
        _background_bulk_process,
        job_id,
        files_data,
        user["username"],
        invoice_type,
        execution_folder,
    )

    return {"job_id": job_id, "accepted": len(files), "filenames": filenames, "execution_folder": execution_folder}


@router.get("/paged")
async def get_invoices_paged_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query(None),
    vendor_name: str = Query(None),
    invoice_number: str = Query(None),
    status: str = Query(None),
    since: str = Query(None),
    until: str = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    user: dict = Depends(get_current_user),
):
    return get_invoices_paged(
        page=page,
        page_size=page_size,
        q=q,
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        status=status,
        since=since,
        until=until,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("/job/{job_id}")
async def get_invoices_for_job(
    job_id: str,
    user: dict = Depends(get_current_user),
):
    return get_invoices_by_job(job_id)


@router.get("/{invoice_id}/download")
async def get_invoice_download_url(
    invoice_id: int,
    user: dict = Depends(get_current_user),
):
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    blob_path = invoice.get("blob_path")
    if not blob_path:
        raise HTTPException(status_code=404, detail="No file stored for this invoice")
    try:
        sas_url = azure_storage_client.generate_sas_url(blob_path)
        return {"download_url": sas_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {e}") from e


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: int,
    user: dict = Depends(get_current_user),
):
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: int,
    user: dict = Depends(get_current_user),
):
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    soft_delete_invoice(invoice_id)
    return {"deleted": True, "id": invoice_id}
