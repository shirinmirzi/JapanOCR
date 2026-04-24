import io
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from psycopg2 import sql

from config.database import get_db_connection
from middleware.entra_auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config")

_ALLOWED_EXTS = {".xlsx", ".xls", ".csv"}
_MASTER_TABLES = {
    "daily": "daily_invoice_master",
    "monthly": "monthly_invoice_master",
}


def _parse_file(filename: str, content: bytes) -> list[dict]:
    """Parse an uploaded Excel or CSV file into a list of row dicts."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, or .csv files are accepted.")

    if ext == ".csv":
        import csv

        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]
    else:
        try:
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not parse Excel file: {exc}") from exc

        if not rows:
            return []
        headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
        result = []
        for row in rows[1:]:
            if all(v is None for v in row):
                continue
            result.append(dict(zip(headers, row)))
        return result


@router.post("/master-upload")
async def upload_master_data(
    file: UploadFile = File(...),
    master_type: str = Form(...),
    _user: dict = Depends(get_current_user),
):
    """Replace all rows in the daily or monthly invoice master table."""
    if master_type not in _MASTER_TABLES:
        raise HTTPException(status_code=400, detail="master_type must be 'daily' or 'monthly'.")

    table = _MASTER_TABLES[master_type]
    content = await file.read()
    rows = _parse_file(file.filename or "upload", content)

    if not rows:
        raise HTTPException(status_code=400, detail="The uploaded file contains no data rows.")

    # Determine first two columns as customer_cd / route_label; rest go to extra JSONB
    all_keys = list(rows[0].keys()) if rows else []
    cd_key = all_keys[0] if len(all_keys) > 0 else None
    label_key = all_keys[1] if len(all_keys) > 1 else None

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Use psycopg2.sql.Identifier to safely compose the table name
            # (table is sourced from the _MASTER_TABLES whitelist, never from user input)
            table_ident = sql.Identifier(table)
            cur.execute(sql.SQL("TRUNCATE TABLE {}").format(table_ident))
            insert_stmt = sql.SQL(
                "INSERT INTO {} (customer_cd, route_label, extra) VALUES (%s, %s, %s)"
            ).format(table_ident)
            for row in rows:
                customer_cd = str(row.get(cd_key, "") or "").strip() if cd_key else None
                route_label = str(row.get(label_key, "") or "").strip() if label_key else None
                extra = {k: v for k, v in row.items() if k not in (cd_key, label_key)}
                cur.execute(
                    insert_stmt,
                    (customer_cd, route_label, extra or None),
                )

    logger.info("Master upload: replaced %d rows in %s", len(rows), table)
    return {"rows_imported": len(rows), "master_type": master_type}
