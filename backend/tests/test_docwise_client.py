"""
Japan OCR Tool - DocWise Client Tests

Unit tests for the OCR response parsing helpers in services.docwise_client.
Covers text extraction, header-line detection, and full invoice field parsing
for both daily and monthly invoice types.

Author: SHIRIN MIRZI M K
"""

import pytest

from services.docwise_client import (
    _is_header_line,
    extract_invoice_data,
    pick_response_text,
)

# =============================================================================
# pick_response_text
# =============================================================================


def test_pick_response_text_returns_empty_for_none() -> None:
    assert pick_response_text(None) == ""


def test_pick_response_text_returns_empty_for_empty_dict() -> None:
    # An empty dict should produce an empty string, not raise.
    assert pick_response_text({}) == ""


def test_pick_response_text_nested_detail_path() -> None:
    response = {
        "detail": {
            "data": {
                "query_response_data": {
                    "response": "172865 | 8039444166 | 2025/04/01"
                }
            }
        }
    }
    assert pick_response_text(response) == "172865 | 8039444166 | 2025/04/01"


def test_pick_response_text_top_level_response_key() -> None:
    assert pick_response_text({"response": "some text"}) == "some text"


def test_pick_response_text_top_level_answer_key() -> None:
    assert pick_response_text({"answer": "extracted answer"}) == "extracted answer"


def test_pick_response_text_falls_back_to_str_when_no_text_key() -> None:
    # When no known key is present the whole dict is stringified as a fallback.
    result = pick_response_text({"unknown_key": 42})
    assert "unknown_key" in result


# =============================================================================
# _is_header_line
# =============================================================================


def test_is_header_line_returns_true_for_known_labels() -> None:
    assert _is_header_line(["CUSTOMER CODE", "INVOICE DATE", "TOTAL AMOUNT"])


def test_is_header_line_case_insensitive() -> None:
    # Labels are matched case-insensitively.
    assert _is_header_line(["customer code", "Invoice Date"])


def test_is_header_line_returns_false_for_data_values() -> None:
    assert not _is_header_line(["172865", "8039444166", "2025/04/01"])


def test_is_header_line_returns_false_for_empty_list() -> None:
    assert not _is_header_line([])


def test_is_header_line_returns_false_for_mixed_content() -> None:
    # Even one unknown part makes the whole line non-header.
    assert not _is_header_line(["CUSTOMER CODE", "172865"])


# =============================================================================
# extract_invoice_data – daily invoices
# =============================================================================


def _make_response(text: str) -> dict:
    """Wrap a plain text string in the nested DocWise response structure."""
    return {
        "detail": {
            "data": {
                "query_response_data": {
                    "response": text
                }
            }
        }
    }


def test_extract_invoice_data_parses_daily_pipe_line() -> None:
    response = _make_response("172865 | 8039444166 | 2025/04/01")
    result = extract_invoice_data(response, invoice_type="daily")
    assert result["customer_code"] == "172865"
    assert result["invoice_number"] == "8039444166"
    assert result["invoice_date"] == "2025/04/01"


def test_extract_invoice_data_skips_header_row_for_daily() -> None:
    # Model sometimes echoes the header before the data row.
    text = "CUSTOMER CODE | DELIVERY NOTE NUMBER | INVOICE DATE\n172865 | 8039444166 | 2025/04/01"
    response = _make_response(text)
    result = extract_invoice_data(response, invoice_type="daily")
    assert result["customer_code"] == "172865"
    assert result["invoice_number"] == "8039444166"


def test_extract_invoice_data_daily_fallback_label_format() -> None:
    # When no pipe-delimited line is found, parse LABEL: value pairs.
    text = (
        "CUSTOMER CODE: 172865\n"
        "DELIVERY NOTE NUMBER: 8039444166\n"
        "INVOICE DATE: 2025/04/01"
    )
    response = _make_response(text)
    result = extract_invoice_data(response, invoice_type="daily")
    assert result["customer_code"] == "172865"
    assert result["invoice_number"] == "8039444166"
    assert result["invoice_date"] == "2025/04/01"


def test_extract_invoice_data_returns_na_for_missing_daily_fields() -> None:
    result = extract_invoice_data(_make_response(""), invoice_type="daily")
    assert result["customer_code"] == "N/A"
    assert result["invoice_number"] == "N/A"
    assert result["invoice_date"] == "N/A"


def test_extract_invoice_data_daily_includes_raw_text() -> None:
    text = "172865 | 8039444166 | 2025/04/01"
    result = extract_invoice_data(_make_response(text), invoice_type="daily")
    assert result["raw_text"] == text


def test_extract_invoice_data_daily_includes_empty_line_items() -> None:
    result = extract_invoice_data(_make_response("172865 | 8039444166 | 2025/04/01"), invoice_type="daily")
    assert result["line_items"] == []


# =============================================================================
# extract_invoice_data – monthly invoices
# =============================================================================


def test_extract_invoice_data_parses_monthly_pipe_line() -> None:
    text = "199621 | 1234567890 | 2025/04/01 | VendorCo | CustomerCo | 10000 | 1000 | 9000 | JPY"
    result = extract_invoice_data(_make_response(text), invoice_type="monthly")
    assert result["customer_code"] == "199621"
    assert result["invoice_number"] == "1234567890"
    assert result["invoice_date"] == "2025/04/01"
    assert result["vendor_name"] == "VendorCo"
    assert result["customer_name"] == "CustomerCo"
    assert result["total_amount"] == "10000"
    assert result["tax_amount"] == "1000"
    assert result["subtotal"] == "9000"
    assert result["currency"] == "JPY"


def test_extract_invoice_data_monthly_parses_line_items() -> None:
    text = (
        "199621 | 1234567890 | 2025/04/01 | VendorCo | CustomerCo | 10000 | 1000 | 9000 | JPY\n"
        "ITEM001 | Widget A | 2 | 4500 | 9000"
    )
    result = extract_invoice_data(_make_response(text), invoice_type="monthly")
    assert len(result["line_items"]) == 1
    item = result["line_items"][0]
    assert item["item_code"] == "ITEM001"
    assert item["item_name"] == "Widget A"
    assert item["quantity"] == "2"
    assert item["unit_price"] == "4500"
    assert item["amount"] == "9000"


def test_extract_invoice_data_monthly_returns_na_for_empty_response() -> None:
    result = extract_invoice_data(_make_response(""), invoice_type="monthly")
    assert result["customer_code"] == "N/A"
    assert result["currency"] == "N/A"


def test_extract_invoice_data_strips_bullet_prefixes() -> None:
    # The model sometimes returns bullet-point-prefixed lines.
    text = "- 172865 | 8039444166 | 2025/04/01"
    result = extract_invoice_data(_make_response(text), invoice_type="daily")
    assert result["customer_code"] == "172865"
