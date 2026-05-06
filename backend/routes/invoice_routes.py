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

import asyncio
import contextlib
import functools
import io
import logging
import os
import re
import tempfile
import threading
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from pypdf import PdfReader, PdfWriter

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
from services.jobs import (
    create_job,
    get_job,
    increment_processed,
    register_job_cancel_event,
    set_current_file,
    set_job_results,
    set_job_status,
    unregister_job_cancel_event,
)
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


def _build_monthly_renamed_filename(
    customer_code: str, coll_invoice_number: str, invoice_date: str
) -> str:
    """Build renamed filename for monthly invoices.

    Format: ``CustomerCode_CollInvoiceNo_YYYYMMDD請求明細書.pdf``

    The date segment is extracted as digits only; if fewer than 8 digits are
    present (e.g. when raw OCR labels leak into the field) today's date is
    used instead.

    ``customer_code`` is sanitized to strip any characters that are invalid in
    Windows filenames (defense-in-depth; callers should have already validated
    the value before reaching this function).
    """
    date_str = re.sub(r"[^0-9]", "", invoice_date or "")[:8] if invoice_date and invoice_date != "N/A" else ""
    if len(date_str) < 8:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    # Strip Windows-invalid characters from customer_code as a final safety
    # layer.  Under normal operation the caller has already validated
    # customer_code, so this is purely defensive.
    safe_code = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", customer_code)
    return f"{safe_code}_{coll_invoice_number}_{date_str}請求明細書.pdf"


def _split_pdf_pages(content: bytes) -> list[bytes]:
    """Split a PDF into a list of single-page PDF byte strings.

    Args:
        content: Raw bytes of the source PDF file.

    Returns:
        List of byte strings, one per page of the original PDF.

    Raises:
        Exception: Propagates any pypdf error so callers can handle it.
    """
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for page in reader.pages:
        writer = PdfWriter()
        writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        pages.append(buf.getvalue())
    return pages


def _process_monthly_page(
    page_content: bytes,
    page_filename: str,
    page_num: int,
    original_filename: str,
    user_id: str,
    job_id: str | None,
    execution_folder: str,
) -> dict:
    """OCR, route, rename, upload, and record a single monthly invoice page.

    Args:
        page_content: Raw bytes of the single-page PDF.
        page_filename: Derived filename used for storage and OCR (e.g.
            ``invoice_page1.pdf``).
        page_num: 1-based page index, embedded in the result dict.
        original_filename: Name of the original multi-page PDF, used only
            for log messages.
        user_id: Username of the uploading user.
        job_id: Optional parent job UUID.
        execution_folder: Shared execution folder for the batch.

    Returns:
        Dict with extracted invoice fields, ``renamed_filename``,
        ``output_folder``, ``blob_url``, ``blob_path``, ``page_number``,
        and optionally ``error``.
    """
    page_log_id = log_processing_start(
        page_filename,
        user_id=user_id,
        execution_folder=execution_folder,
        module="invoice",
    )
    page_invoice_data: dict = {}
    page_ocr_error = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(page_content)
            page_tmp_path = tmp.name
        try:
            with open(page_tmp_path, "rb") as f:
                raw_response = analyze_document(
                    f, page_filename, invoice_type="monthly"
                )
            page_invoice_data = extract_invoice_data(
                raw_response, invoice_type="monthly"
            )
        finally:
            with contextlib.suppress(Exception):
                os.unlink(page_tmp_path)
    except Exception as e:
        logger.error("OCR failed for %s page %d: %s", original_filename, page_num, e)
        page_ocr_error = str(e)

    page_output_folder = "ProcessedFiles"
    page_renamed = None
    if not page_ocr_error:
        customer_code = page_invoice_data.get("customer_code", "N/A")
        coll_invoice_no = page_invoice_data.get("invoice_number", "N/A")
        invoice_date = page_invoice_data.get("invoice_date", "N/A")
        # Only build a monthly filename when the extracted fields are valid.
        # coll_invoice_no must be exactly 10 digits (per spec).
        # customer_code must be purely numeric and 1–9 digits so that:
        #   - raw OCR labels like "ITEM CODE: 8039440753" are rejected (contain
        #     non-digit characters including the colon), and
        #   - 10-digit item codes misidentified as customer codes are rejected
        #     (10-digit numbers match the Coll Invoice No. pattern, not the
        #     customer-code pattern which is typically 5–7 digits).
        _valid_coll_invoice = bool(re.fullmatch(r"\d{10}", coll_invoice_no))
        _safe_customer_code = bool(re.fullmatch(r"\d{1,9}", customer_code))
        if _safe_customer_code and _valid_coll_invoice:
            effective_code, is_do_not_send = _lookup_master(customer_code, "monthly")
            if is_do_not_send:
                page_output_folder = _DO_NOT_SEND_FOLDER
            page_renamed = _build_monthly_renamed_filename(
                effective_code, coll_invoice_no, invoice_date
            )

    # Pages that could not be renamed (OCR error or invalid fields) go to
    # Error instead of ProcessedFiles so they are never silently stored under
    # the raw page filename (e.g. 通常_page3.pdf).
    if page_renamed is None:
        page_output_folder = "Error"

    page_dest = page_renamed if page_renamed else page_filename
    page_blob_path = f"executions/{execution_folder}/{page_output_folder}/{page_dest}"
    page_blob_url = None
    try:
        page_blob_url = azure_storage_client.upload_file(page_content, page_blob_path)
    except Exception as e:
        logger.warning(
            "Failed to upload monthly page %d of %s: %s",
            page_num, original_filename, e,
        )

    page_record = create_invoice(
        job_id=job_id,
        filename=page_filename,
        invoice_data=page_invoice_data,
        blob_url=page_blob_url,
        blob_path=page_blob_path,
        upload_folder=f"executions/{execution_folder}/{page_output_folder}",
        user_id=user_id,
    )

    page_result: dict = {
        **page_invoice_data,
        "id": page_record.get("id"),
        "blob_url": page_blob_url,
        "filename": page_filename,
        "renamed_filename": page_renamed,
        "output_folder": page_output_folder,
        "execution_folder": execution_folder,
        "blob_path": page_blob_path,
        "page_number": page_num,
    }
    # Update the per-page log entry to its terminal state now that the
    # output folder and renamed filename are known.  The routing to "Error"
    # above is the single source of truth, so we key off that here.
    if page_output_folder == "Error":
        update_log_entry(
            page_log_id,
            "error",
            error=(
                page_ocr_error
                if page_ocr_error
                else f"Extracted fields failed validation for page {page_num}"
            ),
            folder_name=page_output_folder,
        )
    else:
        update_log_entry(
            page_log_id,
            "success",
            message=f"Page {page_num} processed",
            renamed_filename=page_renamed,
            folder_name=page_output_folder,
        )

    if page_ocr_error:
        page_result["error"] = page_ocr_error
    return page_result


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


def _process_single_file_sync(
    content: bytes,
    filename: str,
    user_id: str,
    job_id: str = None,
    invoice_type: str = "daily",
    execution_folder: str = None,
) -> dict:
    """
    Run OCR on a single uploaded PDF and persist the result.

    For daily invoices the whole file is sent to DocWise, the extracted fields
    are used to build a renamed filename, and the file is uploaded to Azure.

    For monthly invoices the PDF is first split into individual pages. Each
    page is OCR'd separately to extract the Customer Code, Coll Invoice No.,
    and Invoice Date; each page is renamed as
    ``CustomerCode_CollInvoiceNo_YYYYMMDD請求明細書.pdf`` and uploaded to
    ``ProcessedFiles`` (or ``DoNotSend`` when the master lookup indicates it).

    Args:
        content: Raw bytes of the uploaded PDF.
        filename: Original filename of the uploaded PDF.
        user_id: Username of the uploading user.
        job_id: Optional parent job UUID for bulk-upload context.
        invoice_type: "daily" or "monthly" — selects the OCR prompt and
            field-mapping logic.
        execution_folder: Batch folder name; generated from current UTC time
            if not supplied.

    Returns:
        Dict of extracted invoice fields plus blob_url, blob_path,
        renamed_filename, output_folder, execution_folder, and any error.
        Monthly invoices also include ``pages_processed`` (int) and
        ``all_pages`` (list of per-page result dicts).

    Raises:
        Exception: Re-raises unexpected errors after updating the log entry
            to 'error' so the log always reaches a terminal state.
    """

    if execution_folder is None:
        execution_folder = _build_execution_folder()

    log_id = log_processing_start(
        filename,
        user_id=user_id,
        execution_folder=execution_folder,
        module="invoice",
    )

    try:
        if invoice_type == "monthly":
            # Monthly invoices: split PDF into individual pages, OCR each page,
            # and produce one renamed output file per Coll Invoice No.
            try:
                pages_content = _split_pdf_pages(content)
            except Exception as e:
                logger.error("PDF split failed for %s: %s", filename, e)
                update_log_entry(
                    log_id, "error",
                    error=f"PDF split failed: {e}",
                    folder_name="Error",
                )
                return {
                    "filename": filename,
                    "output_folder": "Error",
                    "execution_folder": execution_folder,
                    "error": str(e),
                    "pages_processed": 0,
                    "all_pages": [],
                }

            page_results = []
            stem, ext = os.path.splitext(filename)
            if not pages_content:
                update_log_entry(
                    log_id, "error",
                    error="PDF has no pages",
                    folder_name="Error",
                )
                return {
                    "filename": filename,
                    "output_folder": "Error",
                    "execution_folder": execution_folder,
                    "error": "PDF has no pages",
                    "pages_processed": 0,
                    "all_pages": [],
                }

            for page_idx, page_content in enumerate(pages_content):
                page_num = page_idx + 1
                page_filename = f"{stem}_page{page_num}{ext}"
                page_result = _process_monthly_page(
                    page_content, page_filename, page_num,
                    filename, user_id, job_id, execution_folder,
                )
                page_results.append(page_result)

            any_success = any(not r.get("error") for r in page_results)
            first = page_results[0]
            overall_folder = first.get("output_folder", "ProcessedFiles")
            log_msg = (
                f"Monthly invoice: {len(page_results)} page(s) processed"
                if any_success else None
            )
            update_log_entry(
                log_id,
                "success" if any_success else "error",
                message=log_msg,
                error=None if any_success else "All monthly invoice pages failed OCR",
                renamed_filename=first.get("renamed_filename"),
                folder_name=overall_folder,
            )
            return {
                "customer_code": first.get("customer_code", "N/A"),
                "invoice_number": first.get("invoice_number", "N/A"),
                "order_number": first.get("order_number", "N/A"),
                "vendor_name": first.get("vendor_name", "N/A"),
                "vendor_address": first.get("vendor_address", "N/A"),
                "customer_name": first.get("customer_name", "N/A"),
                "customer_address": first.get("customer_address", "N/A"),
                "invoice_date": first.get("invoice_date", "N/A"),
                "due_date": first.get("due_date", "N/A"),
                "total_amount": first.get("total_amount", "N/A"),
                "tax_amount": first.get("tax_amount", "N/A"),
                "subtotal": first.get("subtotal", "N/A"),
                "currency": first.get("currency", "N/A"),
                "line_items": first.get("line_items", []),
                "raw_text": first.get("raw_text", ""),
                "id": first.get("id"),
                "blob_url": first.get("blob_url"),
                "filename": filename,
                "renamed_filename": first.get("renamed_filename"),
                "output_folder": first.get("output_folder", "ProcessedFiles"),
                "execution_folder": execution_folder,
                "blob_path": first.get("blob_path"),
                "pages_processed": len(page_results),
                "all_pages": page_results,
            }

        # Daily invoice: OCR the whole file and rename using the standard rule
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

        # Determine output subfolder and renamed filename
        renamed_filename = None
        output_folder = "ProcessedFiles"
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


def _background_bulk_process(job_id: str, files_data: list, user_id: str, invoice_type: str = "daily", execution_folder: str = None, cancel_event: threading.Event | None = None):
    """
    Process a batch of pre-read PDF files in a background thread.

    Updates job status and writes partial results after each file so the
    upload page can display live progress without polling the database.
    Checks the cancel_event (fast in-process signal) and the job's DB status
    before each file so that a cancellation or server-restart interrupt is
    honoured promptly — even while a blocking OCR call is in flight.

    Args:
        job_id: UUID of the parent job record to update throughout.
        files_data: List of dicts, each with 'filename' (str) and
            'content' (bytes) keys.
        user_id: Username of the uploading user, passed through to logs
            and invoice records.
        invoice_type: "daily" or "monthly" — selects OCR prompt and routing.
        execution_folder: Shared execution folder name for all files in this
            batch; generated from current UTC time if not supplied.
        cancel_event: Optional threading.Event registered by the request
            handler.  When set the thread stops at its next check point
            without waiting for a DB poll.
    """
    if execution_folder is None:
        execution_folder = _build_execution_folder()
    set_job_status(job_id, "processing")
    results = {}
    total = len(files_data)
    for idx, item in enumerate(files_data):
        # Check for cancellation — fast in-process event first, then DB fallback.
        # Treat any non-running status (including None from a DB error) as a
        # stop signal so the thread never continues in an ambiguous state.
        if cancel_event is not None and cancel_event.is_set():
            current_status = "interrupted"
        else:
            try:
                current_job = get_job(job_id)
                current_status = current_job.get("status") if current_job else "interrupted"
            except Exception:
                current_status = "interrupted"
        if current_status not in ("queued", "processing"):
            logger.info(
                "Job %s: %s — stopping before file %d/%d (%s)",
                job_id, current_status, idx + 1, total, item["filename"],
            )
            set_current_file(job_id, None)
            set_job_results(job_id, results)
            unregister_job_cancel_event(job_id)
            return

        filename = item["filename"]
        content = item["content"]
        logger.info(
            "Job %s: processing file %d/%d — %s",
            job_id, idx + 1, total, filename,
        )
        set_current_file(job_id, filename)

        log_id = log_processing_start(
            filename,
            user_id=user_id,
            execution_folder=execution_folder,
            module="invoice",
        )

        if invoice_type == "monthly":
            # Monthly: split PDF into pages, OCR each page individually.
            try:
                pages_content = _split_pdf_pages(content)
            except Exception as e:
                logger.error("Bulk PDF split failed for %s: %s", filename, e)
                update_log_entry(
                    log_id, "error",
                    error=f"PDF split failed: {e}",
                    folder_name="Error",
                )
                results[filename] = {
                    "status": "failed",
                    "error": str(e),
                    "renamed_filename": None,
                    "output_folder": "Error",
                    "pages_processed": 0,
                }
                set_job_results(job_id, results)
                increment_processed(job_id)
                continue

            stem, ext = os.path.splitext(filename)
            page_results = []
            if not pages_content:
                update_log_entry(
                    log_id, "error",
                    error="PDF has no pages",
                    folder_name="Error",
                )
                results[filename] = {
                    "status": "failed",
                    "error": "PDF has no pages",
                    "renamed_filename": None,
                    "output_folder": "Error",
                    "pages_processed": 0,
                }
                set_job_results(job_id, results)
                increment_processed(job_id)
                continue

            for page_idx, page_content in enumerate(pages_content):
                # Check for cancellation before each blocking OCR page call.
                if cancel_event is not None and cancel_event.is_set():
                    logger.info(
                        "Job %s: cancelled before page %d of %s",
                        job_id, page_idx + 1, filename,
                    )
                    update_log_entry(log_id, "interrupted", error="Job cancelled")
                    set_current_file(job_id, None)
                    set_job_results(job_id, results)
                    unregister_job_cancel_event(job_id)
                    return
                page_num = page_idx + 1
                page_filename = f"{stem}_page{page_num}{ext}"
                page_result = _process_monthly_page(
                    page_content, page_filename, page_num,
                    filename, user_id, job_id, execution_folder,
                )
                page_results.append(page_result)

            any_success = any(not r.get("error") for r in page_results)
            first = page_results[0]
            results[filename] = {
                "status": "done" if any_success else "failed",
                "invoice_number": first.get("invoice_number", "N/A"),
                "vendor_name": first.get("vendor_name", "N/A"),
                "customer_name": first.get("customer_name", "N/A"),
                "invoice_date": first.get("invoice_date", "N/A"),
                "total_amount": first.get("total_amount", "N/A"),
                "renamed_filename": first.get("renamed_filename"),
                "output_folder": first.get("output_folder", "ProcessedFiles"),
                "pages_processed": len(page_results),
                "page_results": page_results,
            }
            if not any_success:
                results[filename]["error"] = "All monthly invoice pages failed OCR"
            bulk_log_msg = (
                f"Monthly invoice: {len(page_results)} page(s) processed"
                if any_success else None
            )
            update_log_entry(
                log_id,
                "success" if any_success else "error",
                message=bulk_log_msg,
                error=None if any_success else "All monthly invoice pages failed OCR",
                renamed_filename=first.get("renamed_filename"),
                folder_name=first.get("output_folder", "ProcessedFiles"),
            )

            set_job_results(job_id, results)
            increment_processed(job_id)
            continue

        # Daily invoice: OCR the whole file and rename using the standard rule
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

        # Check for cancellation after the blocking OCR call completes so the
        # file is not uploaded or recorded when the job has been stopped.
        if cancel_event is not None and cancel_event.is_set():
            logger.info(
                "Job %s: cancelled after OCR for file %d/%d — %s",
                job_id, idx + 1, total, filename,
            )
            update_log_entry(log_id, "interrupted", error="Job cancelled")
            set_current_file(job_id, None)
            set_job_results(job_id, results)
            unregister_job_cancel_event(job_id)
            return

        # Determine output subfolder and renamed filename
        renamed_filename = None
        output_folder = "ProcessedFiles"
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

        # Write partial results immediately so the upload page can show
        # live per-file status updates while the job is still running.
        set_job_results(job_id, results)
        increment_processed(job_id)

    failed = sum(1 for r in results.values() if r.get("status") == "failed")
    final_status = (
        "failed" if failed == len(files_data) else "partial" if failed else "done"
    )
    set_current_file(job_id, None)
    set_job_status(job_id, final_status)
    set_job_results(job_id, results)
    unregister_job_cancel_event(job_id)


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
    content = await file.read()
    result = await asyncio.get_running_loop().run_in_executor(
        None,
        functools.partial(
            _process_single_file_sync,
            content,
            file.filename,
            user["username"],
            invoice_type=invoice_type,
        ),
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

    cancel_event = register_job_cancel_event(job_id)
    background_tasks.add_task(
        _background_bulk_process,
        job_id,
        files_data,
        user["username"],
        invoice_type,
        execution_folder,
        cancel_event,
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
