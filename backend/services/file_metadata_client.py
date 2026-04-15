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
    allowed_sort = {"created_at", "vendor_name", "invoice_number", "status", "invoice_date", "total_amount"}
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
    data_sql = f"SELECT * FROM invoices {where} ORDER BY {sort_by} {sort_dir} LIMIT %s OFFSET %s"
    rows = execute_query(data_sql, params + [page_size, offset])
    items = [dict(r) for r in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def get_invoice_by_id(invoice_id: int) -> dict:
    rows = execute_query("SELECT * FROM invoices WHERE id = %s", (invoice_id,))
    if rows:
        return dict(rows[0])
    return None


def get_invoices_by_job(job_id: str) -> list:
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
    row = execute_write(
        """
        INSERT INTO invoices (
            job_id, filename, invoice_number, vendor_name, vendor_address,
            customer_name, customer_address, invoice_date, due_date,
            total_amount, tax_amount, subtotal, currency, line_items,
            raw_text, blob_url, blob_path, upload_folder, status, user_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
            %s, %s, %s, %s, 'processed', %s
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
        ),
    )
    return dict(row) if row else {}


def update_invoice_status(invoice_id: int, status: str):
    execute_write(
        "UPDATE invoices SET status = %s WHERE id = %s",
        (status, invoice_id),
    )


def soft_delete_invoice(invoice_id: int):
    execute_write(
        "UPDATE invoices SET status = 'deleted' WHERE id = %s",
        (invoice_id,),
    )


def get_dashboard_stats() -> dict:
    status_rows = execute_query(
        "SELECT status, COUNT(*) as count FROM invoices WHERE status != 'deleted' GROUP BY status"
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
    vendors = [{"vendor_name": r["vendor_name"], "count": r["count"]} for r in vendor_rows] if vendor_rows else []

    return {"by_status": by_status, "vendors": vendors}
