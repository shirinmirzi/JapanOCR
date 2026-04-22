import contextlib
import logging
import os
import re
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile

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
from services.logging_client import log_invoice_result

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/invoices")


def _build_upload_folder() -> str:
    now = datetime.now(timezone.utc)
    return f"uploads/{now.strftime('%Y/%m/%d')}"


def _build_execution_folder(user_date: str = None) -> str:
    """Returns e.g. '20250430_143022' or '20250422_143022' if no date given."""
    now = datetime.now(timezone.utc)
    if user_date and re.fullmatch(r'\d{8}', user_date):
        date_part = user_date
    else:
        date_part = now.strftime('%Y%m%d')
    time_part = now.strftime('%H%M%S')
    return f"{date_part}_{time_part}"


def _build_renamed_filename(customer_code: str, invoice_number: str, invoice_date: str, user_date: str = None) -> str:
    """Build renamed filename: CustomerCode_InvoiceNumber_YYYYMMDD納品書兼請求書.pdf"""
    if user_date:
        date_str = user_date
    elif invoice_date and invoice_date != "N/A":
        date_str = invoice_date.replace("/", "").replace("-", "")
    else:
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
    return f"{customer_code}_{invoice_number}_{date_str}納品書兼請求書.pdf"


async def _process_single_file(
    file: UploadFile,
    user_id: str,
    job_id: str = None,
    invoice_type: str = "daily",
    user_date: str = None,
    execution_folder: str = None,
) -> dict:
    content = await file.read()
    filename = file.filename

    if execution_folder is None:
        execution_folder = _build_execution_folder(user_date)

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
            renamed_filename = _build_renamed_filename(
                customer_code, invoice_number, invoice_date, user_date
            )

    dest_name = renamed_filename if renamed_filename else filename
    blob_path = f"executions/{execution_folder}/{output_folder}/{dest_name}"

    blob_url = None
    try:
        blob_url = azure_storage_client.upload_file(content, blob_path)
    except Exception as e:
        logger.warning("Failed to upload %s to Azure: %s", dest_name, e)

    if ocr_error:
        log_invoice_result(
            filename,
            "error",
            error=ocr_error,
            user_id=user_id,
            folder_name=output_folder,
            execution_folder=execution_folder,
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

    record = create_invoice(
        job_id=job_id,
        filename=filename,
        invoice_data=invoice_data,
        blob_url=blob_url,
        blob_path=blob_path,
        upload_folder=f"executions/{execution_folder}/{output_folder}",
        user_id=user_id,
    )
    log_invoice_result(
        filename,
        "success",
        message="Invoice processed",
        user_id=user_id,
        renamed_filename=renamed_filename,
        folder_name=output_folder,
        execution_folder=execution_folder,
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


def _background_bulk_process(job_id: str, files_data: list, user_id: str, invoice_type: str = "daily", execution_folder: str = None):
    if execution_folder is None:
        execution_folder = _build_execution_folder()
    set_job_status(job_id, "processing")
    results = {}
    for item in files_data:
        filename = item["filename"]
        content = item["content"]

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
            user_date = item.get("user_date")
            if ocr_error or customer_code == "N/A" or invoice_number == "N/A":
                output_folder = "Error"
            else:
                renamed_filename = _build_renamed_filename(
                    customer_code, invoice_number, invoice_date, user_date
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
            log_invoice_result(
                filename,
                "error",
                error=ocr_error,
                user_id=user_id,
                folder_name=output_folder,
                execution_folder=execution_folder,
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
            log_invoice_result(
                filename,
                "success",
                message="Bulk invoice processed",
                user_id=user_id,
                renamed_filename=renamed_filename,
                folder_name=output_folder,
                execution_folder=execution_folder,
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
    user_date: str = Form(None),
    user: dict = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    if invoice_type not in _VALID_INVOICE_TYPES:
        raise HTTPException(status_code=400, detail="invoice_type must be 'daily' or 'monthly'")
    if user_date and not re.fullmatch(r'\d{8}', user_date):
        raise HTTPException(status_code=400, detail="user_date must be exactly 8 digits (YYYYMMDD)")
    result = await _process_single_file(
        file, user["username"], invoice_type=invoice_type, user_date=user_date
    )
    return result


@router.post("/bulk-upload")
async def bulk_upload_invoices(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    invoice_type: str = Form("daily"),
    user_date: str = Form(None),
    user: dict = Depends(get_current_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    if invoice_type not in _VALID_INVOICE_TYPES:
        raise HTTPException(status_code=400, detail="invoice_type must be 'daily' or 'monthly'")
    if user_date and not re.fullmatch(r'\d{8}', user_date):
        raise HTTPException(status_code=400, detail="user_date must be exactly 8 digits (YYYYMMDD)")

    execution_folder = _build_execution_folder(user_date)
    filenames = [f.filename for f in files]
    job_id = create_job(filenames=filenames, user_id=user["username"])

    files_data = []
    for f in files:
        content = await f.read()
        files_data.append({"filename": f.filename, "content": content, "user_date": user_date})

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
