"""
Japan OCR Tool - Invoice Metadata Client

Data-access layer for the invoices table. Provides paginated listing,
single-record retrieval, creation, status updates, soft deletion, and
aggregated dashboard statistics.

Key Features:
- Paginated queries: configurable page size with total-count metadata
- Soft delete: marks records as 'deleted' rather than removing them
- Dashboard stats: per-status counts and top-10 vendor aggregations
- Flexible filtering: search by vendor, invoice number, status, date range

Dependencies: psycopg2 (via config.database)
Author: SHIRIN MIRZI M K
"""

import json
import logging

from config.database import execute_query, execute_write

logger = logging.getLogger(__name__)


def get_invoices_paged(
    page: int = 1,
    page_size: int = 20,
    q: str = None,
    vendor_name: str = None,
    invoice_number: str = None,
    status: str = None,
    since: str = None,
    until: str = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> dict:
    """
    Return a paginated, filtered list of non-deleted invoice records.

    Args:
        page: 1-based page number.
        page_size: Maximum records per page.
        q: Free-text search applied to vendor_name, invoice_number,
            and filename (case-insensitive ILIKE).
        vendor_name: Optional vendor name filter (partial match).
        invoice_number: Optional invoice number filter (partial match).
        status: Exact status value to filter on (e.g. "processed").
        since: ISO timestamp lower bound on created_at (inclusive).
        until: ISO timestamp upper bound on created_at (inclusive).
        sort_by: Column name to sort by; defaults to "created_at".
        sort_dir: "asc" or "desc" sort direction; defaults to "desc".

    Returns:
        Dict with keys: items (list of invoice dicts), total, page,
        page_size, and total_pages.
    """
    allowed_sort = {
        "created_at",
        "vendor_name",
        "invoice_number",
        "status",
        "invoice_date",
        "total_amount",
    }
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    sort_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"

    conditions = ["status != 'deleted'"]
    params = []

    if q:
        conditions.append("(vendor_name ILIKE %s OR invoice_number ILIKE %s OR filename ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    if vendor_name:
        conditions.append("vendor_name ILIKE %s")
        params.append(f"%{vendor_name}%")

    if invoice_number:
        conditions.append("invoice_number ILIKE %s")
        params.append(f"%{invoice_number}%")

    if status:
        conditions.append("status = %s")
        params.append(status)

    if since:
        conditions.append("created_at >= %s")
        params.append(since)

    if until:
        conditions.append("created_at <= %s")
        params.append(until)

    where = "WHERE " + " AND ".join(conditions)
    count_sql = f"SELECT COUNT(*) as total FROM invoices {where}"
    count_row = execute_query(count_sql, params or None)
    total = count_row[0]["total"] if count_row else 0

    offset = (page - 1) * page_size
    data_sql = (
        f"SELECT * FROM invoices {where} ORDER BY {sort_by} "
        f"{sort_dir} LIMIT %s OFFSET %s"
    )
    rows = execute_query(data_sql, (params or []) + [page_size, offset])
    items = [dict(r) for r in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def get_invoice_by_id(invoice_id: int) -> dict:
    """
    Fetch a single invoice record by its primary key.

    Args:
        invoice_id: Integer primary key of the invoice row.

    Returns:
        Invoice record as a dict, or None when no row matches.
    """
    rows = execute_query("SELECT * FROM invoices WHERE id = %s", (invoice_id,))
    if rows:
        return dict(rows[0])
    return None


def get_invoices_by_job(job_id: str) -> list:
    """
    Return all invoice records associated with a given job, ordered by id.

    Args:
        job_id: UUID string of the parent job.

    Returns:
        List of invoice dicts; empty list when no records match.
    """
    rows = execute_query(
        "SELECT * FROM invoices WHERE job_id = %s ORDER BY id",
        (job_id,),
    )
    return [dict(r) for r in rows]


def create_invoice(
    job_id: str,
    filename: str,
    invoice_data: dict,
    blob_url: str,
    blob_path: str,
    upload_folder: str,
    user_id: str = None,
) -> dict:
    """
    Insert a new invoice record and return the created row.

    Args:
        job_id: UUID of the parent bulk-upload job (may be None for single
            uploads not associated with a job).
        filename: Original uploaded filename.
        invoice_data: Dict of extracted fields (invoice_number, vendor_name,
            line_items, etc.) as returned by extract_invoice_data.
        blob_url: Public URL or local URI where the PDF is stored.
        blob_path: Relative blob path used for SAS URL generation.
        upload_folder: Logical folder path recorded for UI display.
        user_id: Username of the uploading user, or None.

    Returns:
        The newly created invoice row as a dict, or an empty dict on failure.
    """
    row = execute_write(
        """
        INSERT INTO invoices (
            job_id, filename, invoice_number, vendor_name, vendor_address,
            customer_name, customer_address, invoice_date, due_date,
            total_amount, tax_amount, subtotal, currency, line_items,
            raw_text, blob_url, blob_path, upload_folder, status, user_id,
            customer_code, order_number
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
            %s, %s, %s, %s, 'processed', %s, %s, %s
        )
        RETURNING *
        """,
        (
            job_id,
            filename,
            invoice_data.get("invoice_number"),
            invoice_data.get("vendor_name"),
            invoice_data.get("vendor_address"),
            invoice_data.get("customer_name"),
            invoice_data.get("customer_address"),
            invoice_data.get("invoice_date"),
            invoice_data.get("due_date"),
            invoice_data.get("total_amount"),
            invoice_data.get("tax_amount"),
            invoice_data.get("subtotal"),
            invoice_data.get("currency"),
            json.dumps(invoice_data.get("line_items", [])),
            invoice_data.get("raw_text"),
            blob_url,
            blob_path,
            upload_folder,
            user_id,
            invoice_data.get("customer_code"),
            invoice_data.get("order_number"),
        ),
    )
    return dict(row) if row else {}


def update_invoice_status(invoice_id: int, status: str):
    """
    Update the status column of an existing invoice record.

    Args:
        invoice_id: Integer primary key of the invoice to update.
        status: New status string (e.g. "processed", "error").
    """
    execute_write(
        "UPDATE invoices SET status = %s WHERE id = %s",
        (status, invoice_id),
    )


def soft_delete_invoice(invoice_id: int):
    """
    Mark an invoice as deleted without removing the row from the database.

    Args:
        invoice_id: Integer primary key of the invoice to soft-delete.
    """
    execute_write(
        "UPDATE invoices SET status = 'deleted' WHERE id = %s",
        (invoice_id,),
    )


def get_dashboard_stats() -> dict:
    """
    Compute aggregated statistics used by the dashboard KPI panel.

    Returns:
        Dict with keys:
            by_status: Mapping of status string to invoice count.
            vendors: List of up to 10 dicts (vendor_name, count) ordered
                by count descending, excluding deleted and N/A records.
    """
    status_rows = execute_query(
        "SELECT status, COUNT(*) as count FROM invoices "
        "WHERE status != 'deleted' GROUP BY status"
    )
    by_status = {r["status"]: r["count"] for r in status_rows} if status_rows else {}

    vendor_rows = execute_query(
        """
        SELECT vendor_name, COUNT(*) as count
        FROM invoices
        WHERE status != 'deleted' AND vendor_name IS NOT NULL AND vendor_name != 'N/A'
        GROUP BY vendor_name
        ORDER BY count DESC
        LIMIT 10
        """
    )
    vendors = (
        [{"vendor_name": r["vendor_name"], "count": r["count"]} for r in vendor_rows]
        if vendor_rows
        else []
    )

    return {"by_status": by_status, "vendors": vendors}
