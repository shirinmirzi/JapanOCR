"""
Japan OCR Tool - Configuration Routes

Handles bulk upload and retrieval of master data files used for invoice
routing. Supports Excel (.xlsx/.xlsm) and CSV formats.

Key Features:
- Master upload: replaces all rows for a given type (daily/monthly) atomically
- Master retrieval: returns current rows ordered by original source row number
- Input validation: whitelist-based table selection, row-level validation
- Security: table name composed via psycopg2.sql.Identifier to prevent injection

Dependencies: FastAPI, psycopg2, openpyxl (optional, for Excel parsing)
Author: SHIRIN MIRZI M K
"""

import csv
import io
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from psycopg2 import sql

from config.database import get_db_connection
from middleware.entra_auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/config")

_VALID_MASTER_TYPES = {"daily", "monthly"}

_MASTER_TABLE = {
    "daily": "daily_invoice_master",
    "monthly": "monthly_invoice_master",
}


def _parse_excel(content: bytes) -> list[dict]:
    """Parse an xlsx/xlsm workbook.

    Row 1 is treated as the header row and is skipped.
    Returns rows as dicts with keys customer_cd, destination_cd, and source_row
    where source_row is the 1-based original Excel row number for traceability.
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise HTTPException(
            status_code=500, detail="openpyxl is required for Excel parsing"
        ) from exc

    wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
    ws = wb.active
    rows = []
    for excel_row_num, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if excel_row_num == 1:
            # Skip the header row (Customer CD., 送付先 CD., …)
            continue
        if all(cell is None for cell in row):
            continue
        customer_cd = str(row[0]).strip() if row[0] is not None else ""
        destination_cd = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        rows.append(
            {"customer_cd": customer_cd, "destination_cd": destination_cd, "source_row": excel_row_num}
        )
    return rows


def _parse_csv(content: bytes) -> list[dict]:
    """Parse a UTF-8 CSV file.

    Row 1 is treated as the header row and is skipped.
    Returns rows as dicts with keys customer_cd, destination_cd, and source_row
    where source_row is the 1-based original CSV row number for traceability.
    """
    text = content.decode("utf-8-sig")  # handles BOM if present
    reader = csv.reader(io.StringIO(text))
    rows = []
    for csv_row_num, row in enumerate(reader, start=1):
        if csv_row_num == 1:
            # Skip the header row
            continue
        if not any(cell.strip() for cell in row):
            continue
        customer_cd = row[0].strip() if len(row) > 0 else ""
        destination_cd = row[1].strip() if len(row) > 1 else ""
        rows.append(
            {"customer_cd": customer_cd, "destination_cd": destination_cd, "source_row": csv_row_num}
        )
    return rows


def _validate_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split rows into valid and invalid (missing required columns) lists.

    The source_row key (original Excel/CSV row number) is used as row_number
    when present; otherwise a 1-based sequential index is used as a fallback.
    """
    valid, invalid = [], []
    for i, row in enumerate(rows, start=1):
        row_number = row.get("source_row", i)
        if not row["customer_cd"]:
            invalid.append({"row": row_number, "reason": "customer_cd is empty", "data": row})
        else:
            data = {k: v for k, v in row.items() if k != "source_row"}
            valid.append({**data, "row_number": row_number})
    return valid, invalid


@router.post("/master-upload")
async def upload_master_data(
    master_type: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """
    Bulk-upload a master data Excel or CSV file into the correct DB table.

    - master_type: "daily" or "monthly"
    - file: .xlsx, .xlsm, or .csv (UTF-8) containing customer_cd in col A
            and destination_cd in col B.

    Existing rows in the target table are replaced on each upload.
    Japanese text values (e.g. 送付無し, 破棄) are preserved as-is.
    """
    if master_type not in _VALID_MASTER_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"master_type must be one of: {', '.join(sorted(_VALID_MASTER_TYPES))}",
        )

    filename = file.filename or ""
    content = await file.read()

    lower = filename.lower()
    if lower.endswith(".csv"):
        try:
            rows = _parse_csv(content)
        except Exception as exc:
            logger.error("CSV parse error for %s: %s", filename, exc)
            raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}") from exc
    elif lower.endswith((".xlsx", ".xlsm")):
        try:
            rows = _parse_excel(content)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Excel parse error for %s: %s", filename, exc)
            raise HTTPException(
                status_code=400, detail=f"Failed to parse Excel file: {exc}"
            ) from exc
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a .xlsx, .xlsm, or .csv file.",
        )

    if not rows:
        raise HTTPException(status_code=400, detail="The uploaded file contains no data rows.")

    valid_rows, invalid_rows = _validate_rows(rows)

    table = _MASTER_TABLE[master_type]
    # table is sourced from the _MASTER_TABLE whitelist — never from user input.
    # We use psycopg2.sql.Identifier to compose SQL safely.
    table_ident = sql.Identifier(table)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Replace existing master data for this type
            cur.execute(sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY").format(table_ident))

            if valid_rows:
                values = [
                    (r["customer_cd"], r["destination_cd"], r["row_number"])
                    for r in valid_rows
                ]
                # Use executemany for bulk insert; psycopg2 batches this efficiently
                cur.executemany(
                    sql.SQL(
                        "INSERT INTO {} (customer_cd, destination_cd, row_number) "
                        "VALUES (%s, %s, %s)"
                    ).format(table_ident),
                    values,
                )

    logger.info(
        "Master upload: type=%s file=%s inserted=%d skipped=%d user=%s",
        master_type,
        filename,
        len(valid_rows),
        len(invalid_rows),
        user.get("username"),
    )

    return {
        "master_type": master_type,
        "filename": filename,
        "inserted": len(valid_rows),
        "skipped": len(invalid_rows),
        "invalid_rows": invalid_rows,
    }


@router.get("/master-data/{master_type}")
def get_master_data(
    master_type: str,
    user: dict = Depends(get_current_user),
):
    """Return the current rows for the given master type (daily or monthly)."""
    if master_type not in _VALID_MASTER_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"master_type must be one of: {', '.join(sorted(_VALID_MASTER_TYPES))}",
        )
    table = _MASTER_TABLE[master_type]
    table_ident = sql.Identifier(table)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "SELECT id, customer_cd, destination_cd, row_number, created_at "
                    "FROM {} ORDER BY row_number ASC NULLS LAST, id ASC"
                ).format(table_ident)
            )
            rows = cur.fetchall()
    return {"master_type": master_type, "count": len(rows), "rows": [dict(r) for r in rows]}
