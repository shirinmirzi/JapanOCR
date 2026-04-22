import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

DOCWISE_URL = os.environ.get(
    "DOCWISE_URL",
    "https://docwiseapi-dev.getinge.com/v1/docwise/analyze",
)
DOCWISE_DAILY_PROMPT = (
    "This is a Japanese Delivery Note and Invoice (納品書兼請求書). "
    "Extract ONLY the following 3 fields and return them pipe-separated on ONE line: "
    "CUSTOMER CODE | DELIVERY NOTE NUMBER | INVOICE DATE. "
    "Field definitions: "
    "CUSTOMER CODE = the value next to the label '顧客番号' in the detail table on the right side of the document. "
    "DELIVERY NOTE NUMBER = the large bold number displayed prominently in the document title header area, "
    "immediately next to or below the text '納品書兼請求書'. "
    "This is the document identifier shown in the title box (e.g. 8039444200). "
    "It is NOT the 受注伝票番号, NOT the 納品書番号, NOT the 顧客番号 from the table rows. "
    "INVOICE DATE = the date shown in the title header area next to the document number, format YYYY/MM/DD. "
    "Do NOT include a header row. Output data values only, one line. Use N/A for missing fields."
)

DOCWISE_MONTHLY_PROMPT = (
    "This is a Japanese Monthly Invoice Statement (請求明細書). "
    "Extract the following fields and return them pipe-separated on ONE line: "
    "CUSTOMER CODE | COLL INVOICE NUMBER | INVOICE DATE | VENDOR NAME | CUSTOMER NAME | TOTAL AMOUNT | TAX AMOUNT | SUBTOTAL | CURRENCY. "
    "Field definitions: "
    "CUSTOMER CODE = customer code found in the last line of the address block, just before the Japanese text 御中. It is typically 6 digits. "
    "COLL INVOICE NUMBER = the collective invoice number, exactly 10 digits. "
    "INVOICE DATE = invoice date in YYYY/MM/DD format. "
    "CURRENCY = JPY. "
    "Do NOT include a header row. Output data values only, one line. Use N/A for missing fields. "
    "Then list each line item as: ITEM CODE | ITEM NAME | QUANTITY | UNIT PRICE | AMOUNT."
)

MAX_ATTEMPTS = int(os.environ.get("DOCWISE_MAX_ATTEMPTS", 3))
BACKOFF_BASE_SEC = float(os.environ.get("DOCWISE_BACKOFF_BASE_SEC", 2))
TIMEOUT_SEC = float(os.environ.get("DOCWISE_TIMEOUT_SEC", 120))


def pick_response_text(docwise_response: dict) -> str:
    if not docwise_response:
        return ""
    # Try nested paths in order (DocWise returns text at detail.data.query_response_data.response)
    paths = [
        ["detail", "data", "query_response_data", "response"],
        ["data", "query_response_data", "response"],
        ["query_response_data", "response"],
        ["detail", "response"],
        ["response"],
    ]
    for path in paths:
        node = docwise_response
        for key in path:
            if not isinstance(node, dict):
                break
            node = node.get(key)
        else:
            if node:
                if isinstance(node, str):
                    return node
                if isinstance(node, dict):
                    for sub_key in ("content", "text"):
                        val = node.get(sub_key)
                        if val and isinstance(val, str):
                            return val
    # Fall back to top-level keys
    for key in ["answer", "text", "content", "result", "output", "response"]:
        val = docwise_response.get(key)
        if val and isinstance(val, str):
            return val
    return str(docwise_response)


def analyze_document(file_obj, filename: str, query: str = None, invoice_type: str = "daily") -> dict:
    api_key = os.environ.get("DOCWISE_API_KEY", "")
    if query:
        prompt = query
    elif invoice_type == "monthly":
        prompt = DOCWISE_MONTHLY_PROMPT
    else:
        prompt = DOCWISE_DAILY_PROMPT

    headers = {}
    api_key = api_key.strip()
    if api_key:
        headers["Authorization"] = f"DOCWISE {api_key}"

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            file_obj.seek(0)
            files = {"document": (filename, file_obj, "application/pdf")}
            data = {"query": prompt, "length": "Long", "format": "Bullet points"}
            response = requests.post(
                DOCWISE_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=TIMEOUT_SEC,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout as e:
            last_error = e
            logger.warning(
                "DocWise timeout on attempt %d/%d for %s",
                attempt,
                MAX_ATTEMPTS,
                filename,
            )
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning(
                "DocWise error on attempt %d/%d for %s: %s",
                attempt,
                MAX_ATTEMPTS,
                filename,
                e,
            )

        if attempt < MAX_ATTEMPTS:
            time.sleep(BACKOFF_BASE_SEC ** attempt)

    raise RuntimeError(
        f"DocWise analysis failed after {MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


_HEADER_LABELS = {
    "INVOICE NUMBER", "VENDOR NAME", "VENDOR ADDRESS", "CUSTOMER NAME",
    "CUSTOMER ADDRESS", "INVOICE DATE", "DUE DATE", "TOTAL AMOUNT",
    "TAX AMOUNT", "SUBTOTAL", "CURRENCY", "CUSTOMER CODE",
    "COLL INVOICE NUMBER", "ORDER NUMBER", "DESCRIPTION", "QUANTITY",
    "UNIT PRICE", "TOTAL", "ITEM CODE", "ITEM NAME", "AMOUNT",
    "DELIVERY NOTE NUMBER",
}


def _is_header_line(parts: list) -> bool:
    """Return True if all pipe-separated parts are known header label words."""
    return bool(parts) and all(p.upper() in _HEADER_LABELS for p in parts if p)


def extract_invoice_data(docwise_response: dict, invoice_type: str = "daily") -> dict:
    raw_text = pick_response_text(docwise_response)
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

    fields = {
        "customer_code": "N/A",
        "invoice_number": "N/A",
        "order_number": "N/A",
        "vendor_name": "N/A",
        "vendor_address": "N/A",
        "customer_name": "N/A",
        "customer_address": "N/A",
        "invoice_date": "N/A",
        "due_date": "N/A",
        "total_amount": "N/A",
        "tax_amount": "N/A",
        "subtotal": "N/A",
        "currency": "N/A",
        "line_items": [],
    }

    if invoice_type == "monthly":
        field_keys = [
            "customer_code",
            "invoice_number",
            "invoice_date",
            "vendor_name",
            "customer_name",
            "total_amount",
            "tax_amount",
            "subtotal",
            "currency",
        ]
    else:
        field_keys = [
            "customer_code",
            "invoice_number",
            "invoice_date",
        ]

    header_parsed = False
    line_item_lines = []

    for line in lines:
        line = line.lstrip("-•* ").strip()
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if _is_header_line(parts):
                # Skip header label rows returned by the model
                continue
            if not header_parsed:
                # First non-header pipe line = header field values
                for i, key in enumerate(field_keys):
                    if i < len(parts):
                        fields[key] = parts[i] if parts[i] else "N/A"
                header_parsed = True
            else:
                # Subsequent pipe lines = line items
                if len(parts) >= 4:
                    line_item_lines.append({
                        "item_code": parts[0],
                        "item_name": parts[1],
                        "quantity": parts[2],
                        "unit_price": parts[3],
                        "amount": parts[4] if len(parts) > 4 else "N/A",
                    })

    # Fallback for daily invoices: parse LABEL: value format when pipe parsing found nothing
    if invoice_type == "daily" and fields["customer_code"] == "N/A" and fields["invoice_number"] == "N/A":
        label_map = {
            "CUSTOMER CODE": "customer_code",
            "DELIVERY NOTE NUMBER": "invoice_number",
            "INVOICE DATE": "invoice_date",
        }
        for line in lines:
            clean = line.lstrip("-•* ").strip()
            for label, field_key in label_map.items():
                if clean.upper().startswith(label + ":"):
                    value = clean[len(label) + 1:].strip()
                    if value:
                        fields[field_key] = value
                    break

    fields["line_items"] = line_item_lines
    fields["raw_text"] = raw_text
    return fields
