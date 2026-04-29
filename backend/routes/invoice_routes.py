"""
Japan OCR Tool - Invoice Processing Routes

Handles single and bulk PDF invoice uploads, orchestrates OCR analysis via
DocWise, routes processed files to the correct output folder, and exposes
CRUD endpoints for the invoice records.

Key Features:
- Single upload: synchronous OCR + Azure upload, result returned immediately
- Bulk upload: files queued in a background task, progress tracked via job_id
- Routing logic: master-table lookup maps customer codes to destination folders
- DoNotSend handling: non-numeric destination codes route to a quarantine folder
- Soft delete: invoice records are flagged 'deleted', not physically removed

Dependencies: FastAPI, psycopg2, azure-storage-blob, services.*
Author: SHIRIN MIRZI M K
"""

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
    """
    Build a date-partitioned upload folder path for the current UTC date.

    Returns:
        Path string in the form "uploads/YYYY/MM/DD".
    """
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
    # An empty destination_cd means the row exists but has no routing code —
    # fall back to the original customer_code without DoNotSend routing.
    if not destination_cd:
        return customer_code, False
    # A destination_cd that is not purely numeric signals a DoNotSend rule
    # (e.g. Japanese words like 送付無し or 破棄).
    if not re.fullmatch(r'\d+', destination_cd):
        return customer_code, True

    return destination_cd, False


def _resolve_routing(
    invoice_data: dict,
    invoice_type: str,
    ocr_error: str | None,
) -> tuple[str, str | None]:
    """Determine the output folder and optional renamed filename for a processed invoice.

    For daily invoices the routing rules are (in priority order):
    1. Any OCR error, or a missing customer_code / invoice_number from the PDF
       → route to the ``Error`` folder; no rename.
    2. The customer code is found in the master table with a non-numeric
       destination_cd (e.g. 送付無し) → route to the ``DoNotSend`` folder;
       rename using the original customer code from the PDF.
    3. The customer code is found in the master table with a numeric
       destination_cd → route to ``ProcessedFiles``; rename using the
       destination_cd as the customer code prefix.
    4. **The customer code is NOT found in the master table** → route to
       ``ProcessedFiles``; rename using the original customer code extracted
       from the PDF.  This is the intended fallback per the business rules:
       the file is still processed and named after the PDF customer code.

    Monthly invoices are not renamed and always land in ``ProcessedFiles``.

    Args:
        invoice_data: Extracted OCR fields (customer_code, invoice_number, …).
        invoice_type: ``"daily"`` or ``"monthly"``.
        ocr_error: Non-empty string when OCR failed; ``None`` otherwise.

    Returns:
        A tuple of ``(output_folder, renamed_filename)`` where
        ``renamed_filename`` is ``None`` when no rename should happen.
    """
    output_folder = "ProcessedFiles"
    renamed_filename = None

    if invoice_type != "daily":
        return output_folder, renamed_filename

    customer_code = invoice_data.get("customer_code", "N/A")
    invoice_number = invoice_data.get("invoice_number", "N/A")
    invoice_date = invoice_data.get("invoice_date", "N/A")

    if ocr_error or customer_code == "N/A" or invoice_number == "N/A":
        return "Error", None

    # Resolve customer_code against the master table.  When the code is not
    # present in the master file, _lookup_master returns the original PDF
    # customer code so the fallback rename still uses a meaningful identifier.
    effective_code, is_do_not_send = _lookup_master(customer_code, invoice_type)
    if is_do_not_send:
        output_folder = _DO_NOT_SEND_FOLDER
    renamed_filename = _build_renamed_filename(effective_code, invoice_number, invoice_date)

    return output_folder, renamed_filename


async def _process_single_file(
    file: UploadFile,
    user_id: str,
    job_id: str = None,
    invoice_type: str = "daily",
    execution_folder: str = None,
) -> dict:
    """
    Run OCR on a single uploaded PDF and persist the result.

    Uploads the file to Azure (or local storage), inserts an invoice record,
    and writes a log entry capturing the outcome.

    Args:
        file: The uploaded PDF UploadFile object.
        user_id: Username of the uploading user.
        job_id: Optional parent job UUID for bulk-upload context.
        invoice_type: "daily" or "monthly" — selects the OCR prompt and
            field-mapping logic.
        execution_folder: Batch folder name; generated from current UTC time
            if not supplied.

    Returns:
        Dict of extracted invoice fields plus blob_url, blob_path,
        renamed_filename, output_folder, execution_folder, and any error.

    Raises:
        Exception: Re-raises unexpected errors after updating the log entry
            to 'error' so the log always reaches a terminal state.
    """
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
        output_folder, renamed_filename = _resolve_routing(invoice_data, invoice_type, ocr_error)

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
    """
    Process a batch of pre-read PDF files in a background thread.

    Updates job status and writes partial results after each file so the
    upload page can display live progress without polling the database.

    Args:
        job_id: UUID of the parent job record to update throughout.
        files_data: List of dicts, each with 'filename' (str) and
            'content' (bytes) keys.
        user_id: Username of the uploading user, passed through to logs
            and invoice records.
        invoice_type: "daily" or "monthly" — selects OCR prompt and routing.
        execution_folder: Shared execution folder name for all files in this
            batch; generated from current UTC time if not supplied.
    """
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
        output_folder, renamed_filename = _resolve_routing(invoice_data, invoice_type, ocr_error)

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

        # Write partial results immediately so the upload page can show
        # live per-file status updates while the job is still running.
        set_job_results(job_id, results)
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
    """
    Process and store a single PDF invoice synchronously.

    Args:
        file: PDF file upload (must have a .pdf extension).
        invoice_type: "daily" or "monthly"; defaults to "daily".
        user_date: Ignored — accepted only for backward compatibility.
        user: Injected authenticated user.

    Returns:
        Dict of extracted invoice fields plus storage metadata.

    Raises:
        HTTPException: 400 for non-PDF uploads or invalid invoice_type.
    """
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
    """
    Queue multiple PDF invoices for background OCR processing.

    Files are read into memory immediately so the request body is consumed
    before the background task runs. Processing status is tracked via the
    returned job_id.

    Args:
        background_tasks: FastAPI BackgroundTasks injected by the framework.
        files: One or more PDF files to process.
        invoice_type: "daily" or "monthly"; defaults to "daily".
        user_date: Ignored — accepted only for backward compatibility.
        user: Injected authenticated user.

    Returns:
        Dict with job_id, accepted (file count), filenames, and
        execution_folder.

    Raises:
        HTTPException: 400 when no files are supplied or invoice_type is
            invalid.
    """
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
    """
    Return a paginated, filterable list of invoice records.

    Returns:
        Paginated response dict (items, total, page, page_size, total_pages).
    """
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
    """
    Return all invoice records that belong to a given bulk-upload job.

    Args:
        job_id: UUID string of the parent job.
        user: Injected authenticated user.

    Returns:
        List of invoice dicts ordered by id.
    """
    return get_invoices_by_job(job_id)


@router.get("/{invoice_id}/download")
async def get_invoice_download_url(
    invoice_id: int,
    user: dict = Depends(get_current_user),
):
    """
    Generate a time-limited download URL for the stored invoice PDF.

    Args:
        invoice_id: Integer primary key of the invoice.
        user: Injected authenticated user.

    Returns:
        Dict with 'download_url' containing an Azure SAS URL or local URI.

    Raises:
        HTTPException: 404 when the invoice or its blob_path is not found;
            500 when SAS URL generation fails.
    """
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
    """
    Return a single invoice record by its primary key.

    Args:
        invoice_id: Integer primary key of the invoice.
        user: Injected authenticated user.

    Returns:
        Invoice record as a dict.

    Raises:
        HTTPException: 404 when no matching invoice is found.
    """
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: int,
    user: dict = Depends(get_current_user),
):
    """
    Soft-delete an invoice record by marking its status as 'deleted'.

    Args:
        invoice_id: Integer primary key of the invoice to delete.
        user: Injected authenticated user.

    Returns:
        Dict with 'deleted': True and the 'id' of the deleted record.

    Raises:
        HTTPException: 404 when no matching invoice is found.
    """
    invoice = get_invoice_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    soft_delete_invoice(invoice_id)
    return {"deleted": True, "id": invoice_id}
