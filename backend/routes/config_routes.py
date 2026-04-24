import csv
import io
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

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

    Returns rows as dicts with keys customer_cd and destination_cd.
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
    for row in ws.iter_rows(values_only=True):
        if all(cell is None for cell in row):
            continue
        customer_cd = str(row[0]).strip() if row[0] is not None else ""
        destination_cd = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        rows.append({"customer_cd": customer_cd, "destination_cd": destination_cd})
    return rows


def _parse_csv(content: bytes) -> list[dict]:
    """Parse a UTF-8 CSV file and return rows as dicts with keys customer_cd and destination_cd."""
    text = content.decode("utf-8-sig")  # handles BOM if present
    reader = csv.reader(io.StringIO(text))
    rows = []
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        customer_cd = row[0].strip() if len(row) > 0 else ""
        destination_cd = row[1].strip() if len(row) > 1 else ""
        rows.append({"customer_cd": customer_cd, "destination_cd": destination_cd})
    return rows


def _validate_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split rows into valid and invalid (missing required columns) lists."""
    valid, invalid = [], []
    for i, row in enumerate(rows, start=1):
        if not row["customer_cd"]:
            invalid.append({"row": i, "reason": "customer_cd is empty", "data": row})
        else:
            valid.append({**row, "row_number": i})
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
    # Explicit allowlist check: table must be one of the two known names.
    # This is guaranteed by _VALID_MASTER_TYPES + _MASTER_TABLE, but we
    # assert it here so static-analysis tools can confirm there is no
    # user-controlled SQL construction.
    assert table in ("daily_invoice_master", "monthly_invoice_master")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Replace existing master data for this type
            cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY")

            if valid_rows:
                values = [
                    (r["customer_cd"], r["destination_cd"], r["row_number"])
                    for r in valid_rows
                ]
                # Use executemany for bulk insert; psycopg2 batches this efficiently
                cur.executemany(
                    f"INSERT INTO {table} (customer_cd, destination_cd, row_number) "
                    "VALUES (%s, %s, %s)",
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
async def get_master_data(
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
    # Explicit allowlist check — same guarantee as in the upload endpoint.
    assert table in ("daily_invoice_master", "monthly_invoice_master")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, customer_cd, destination_cd, row_number, created_at "
                f"FROM {table} ORDER BY row_number ASC NULLS LAST, id ASC"
            )
            rows = cur.fetchall()
    return {"master_type": master_type, "count": len(rows), "rows": [dict(r) for r in rows]}
