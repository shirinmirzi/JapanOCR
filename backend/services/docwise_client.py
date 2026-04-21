import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

DOCWISE_URL = os.environ.get(
    "DOCWISE_URL",
    "https://docwiseapi-dev.getinge.com/v1/docwise/analyze",
)
DOCWISE_INVOICE_PROMPT = (
    "Extract all invoice data from this document. "
    "Return the following fields in pipe-separated format: "
    "INVOICE NUMBER | VENDOR NAME | VENDOR ADDRESS | CUSTOMER NAME | CUSTOMER ADDRESS | "
    "INVOICE DATE | DUE DATE | TOTAL AMOUNT | TAX AMOUNT | SUBTOTAL | CURRENCY. "
    "Then list each line item as: DESCRIPTION | QUANTITY | UNIT PRICE | TOTAL. "
    "Preserve all numbers exactly as printed. "
    "If a field is not found, use N/A."
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


def analyze_document(file_obj, filename: str, query: str = None) -> dict:
    api_key = os.environ.get("DOCWISE_API_KEY", "")
    prompt = query or DOCWISE_INVOICE_PROMPT

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


def extract_invoice_data(docwise_response: dict) -> dict:
    raw_text = pick_response_text(docwise_response)
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

    fields = {
        "invoice_number": "N/A",
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

    # Parse header fields — expect first line to be pipe-separated header values
    field_keys = [
        "invoice_number",
        "vendor_name",
        "vendor_address",
        "customer_name",
        "customer_address",
        "invoice_date",
        "due_date",
        "total_amount",
        "tax_amount",
        "subtotal",
        "currency",
    ]

    header_line = ""
    line_item_lines = []
    in_line_items = False

    for line in lines:
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if not in_line_items and not header_line:
                # First pipe line = header fields
                for i, key in enumerate(field_keys):
                    if i < len(parts):
                        fields[key] = parts[i] if parts[i] else "N/A"
                header_line = line
            else:
                # Subsequent pipe lines = line items
                in_line_items = True
                if len(parts) >= 4:
                    line_item_lines.append({
                        "description": parts[0],
                        "quantity": parts[1],
                        "unit_price": parts[2],
                        "total": parts[3],
                    })

    fields["line_items"] = line_item_lines
    fields["raw_text"] = raw_text
    return fields
