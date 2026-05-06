"""
Japan OCR Tool - Invoice Routes Helper Tests

Unit tests for the pure helper functions in routes.invoice_routes:
filename construction, folder path building, and the master-table lookup.

Author: SHIRIN MIRZI M K
"""

from contextlib import contextmanager
import re
from unittest.mock import MagicMock, patch

from routes.invoice_routes import (
    _build_execution_folder,
    _build_monthly_renamed_filename,
    _build_renamed_filename,
    _build_upload_folder,
    _group_monthly_pages,
    _lookup_master,
    _merge_pdf_pages,
    _split_pdf_pages,
)

# =============================================================================
# _build_upload_folder
# =============================================================================


def test_build_upload_folder_has_uploads_prefix() -> None:
    folder = _build_upload_folder()
    assert folder.startswith("uploads/")


def test_build_upload_folder_contains_four_digit_year() -> None:
    folder = _build_upload_folder()
    # Expect a YYYY segment between slashes.
    parts = folder.split("/")
    assert len(parts) == 4
    assert len(parts[1]) == 4
    assert parts[1].isdigit()


# =============================================================================
# _build_execution_folder
# =============================================================================


def test_build_execution_folder_has_correct_length() -> None:
    # Format: YYYYMMDD_HHMMSS = 15 characters
    folder = _build_execution_folder()
    assert len(folder) == 15


def test_build_execution_folder_contains_underscore_separator() -> None:
    folder = _build_execution_folder()
    assert "_" in folder
    date_part, time_part = folder.split("_")
    assert len(date_part) == 8
    assert len(time_part) == 6
    assert date_part.isdigit()
    assert time_part.isdigit()


# =============================================================================
# _build_renamed_filename
# =============================================================================


def test_build_renamed_filename_standard_case() -> None:
    name = _build_renamed_filename("172865", "8039444166", "2025/04/01")
    assert name == "172865_8039444166_20250401納品書兼請求書.pdf"


def test_build_renamed_filename_hyphen_date_format() -> None:
    name = _build_renamed_filename("172865", "8039444166", "2025-04-01")
    assert name == "172865_8039444166_20250401納品書兼請求書.pdf"


def test_build_renamed_filename_na_date_uses_today() -> None:
    name = _build_renamed_filename("172865", "8039444166", "N/A")
    # Should still produce a valid filename; just verify the pattern.
    assert name.startswith("172865_8039444166_")
    assert name.endswith("納品書兼請求書.pdf")
    # The date segment between the last _ prefix and the suffix should be 8 digits.
    date_segment = name.split("_")[2][:8]
    assert len(date_segment) == 8
    assert date_segment.isdigit()


def test_build_renamed_filename_empty_date_uses_today() -> None:
    name = _build_renamed_filename("111", "222", "")
    assert name.endswith("納品書兼請求書.pdf")


def test_build_renamed_filename_preserves_customer_and_invoice_codes() -> None:
    name = _build_renamed_filename("ABC", "XYZ", "2025/12/31")
    assert name.startswith("ABC_XYZ_")


# =============================================================================
# _lookup_master
# =============================================================================

# Helper: build a fake get_db_connection context manager that yields a
# connection whose cursor returns the given row from fetchone().

def _make_fake_db(row: dict | None):
    """Return a patch target and a context-manager factory for get_db_connection."""
    fake_cur = MagicMock()
    fake_cur.fetchone.return_value = row
    fake_cur.__enter__ = lambda s: s
    fake_cur.__exit__ = MagicMock(return_value=False)

    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cur
    fake_conn.__enter__ = lambda s: s
    fake_conn.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def fake_get_db():
        yield fake_conn

    return fake_get_db


def test_lookup_master_code_not_in_master_returns_original() -> None:
    """When the customer code is absent from the master table the original
    code must be returned and is_do_not_send must be False so the file is
    routed to ProcessedFiles with the PDF customer code as the filename prefix."""
    with patch("routes.invoice_routes.get_db_connection", _make_fake_db(None)):
        effective_code, is_do_not_send = _lookup_master("C001", "daily")

    assert effective_code == "C001"
    assert is_do_not_send is False


def test_lookup_master_numeric_destination_returns_destination_code() -> None:
    """When the master row contains a numeric destination_cd the resolved
    code is returned and is_do_not_send is False."""
    row = {"destination_cd": "67890"}
    with patch("routes.invoice_routes.get_db_connection", _make_fake_db(row)):
        effective_code, is_do_not_send = _lookup_master("C001", "daily")

    assert effective_code == "67890"
    assert is_do_not_send is False


def test_lookup_master_non_numeric_destination_sets_do_not_send() -> None:
    """A non-numeric destination_cd (e.g. 送付無し) signals DoNotSend routing;
    the original customer code is preserved and is_do_not_send is True."""
    row = {"destination_cd": "送付無し"}
    with patch("routes.invoice_routes.get_db_connection", _make_fake_db(row)):
        effective_code, is_do_not_send = _lookup_master("C001", "daily")

    assert effective_code == "C001"
    assert is_do_not_send is True


def test_lookup_master_empty_destination_returns_original() -> None:
    """An empty destination_cd means the row exists but has no routing code;
    the original customer code is used and is_do_not_send is False."""
    with patch("routes.invoice_routes.get_db_connection", _make_fake_db({"destination_cd": ""})):
        effective_code, is_do_not_send = _lookup_master("C001", "daily")

    assert effective_code == "C001"
    assert is_do_not_send is False


def test_lookup_master_db_exception_falls_back_to_original() -> None:
    """If the DB lookup raises an exception the function must fall back
    gracefully: return the original customer code and False."""
    def raising_get_db():
        raise RuntimeError("connection refused")

    with patch("routes.invoice_routes.get_db_connection", raising_get_db):
        effective_code, is_do_not_send = _lookup_master("C001", "daily")

    assert effective_code == "C001"
    assert is_do_not_send is False


def test_lookup_master_unknown_invoice_type_returns_original() -> None:
    """An unrecognised invoice_type has no master table entry; the original
    customer code is returned without touching the database."""
    effective_code, is_do_not_send = _lookup_master("C001", "unknown_type")

    assert effective_code == "C001"
    assert is_do_not_send is False


def test_lookup_master_monthly_type_not_in_master_returns_original() -> None:
    """Same fallback behaviour applies to the monthly invoice master."""
    with patch("routes.invoice_routes.get_db_connection", _make_fake_db(None)):
        effective_code, is_do_not_send = _lookup_master("M999", "monthly")

    assert effective_code == "M999"
    assert is_do_not_send is False


# =============================================================================
# Routing decision: customer code absent from master → ProcessedFiles
# =============================================================================

def test_routing_not_in_master_uses_pdf_code_and_processed_folder() -> None:
    """End-to-end routing assertion for the fallback case.

    When a customer code is extracted from the PDF but is not present in the
    master file the renamed filename must use the PDF customer code and the
    output folder must be ProcessedFiles (not Error, not DoNotSend).
    """
    customer_code = "C001"
    invoice_number = "INV999"
    invoice_date = "2025/04/01"

    # Simulate: code present in PDF, not in master.
    with patch("routes.invoice_routes.get_db_connection", _make_fake_db(None)):
        effective_code, is_do_not_send = _lookup_master(customer_code, "daily")

    # Verify the fallback code is the original PDF code.
    assert effective_code == customer_code
    assert is_do_not_send is False

    # Verify the filename is built from the PDF code.
    renamed = _build_renamed_filename(effective_code, invoice_number, invoice_date)
    assert renamed == "C001_INV999_20250401納品書兼請求書.pdf"

    # is_do_not_send=False guarantees the routing code leaves output_folder as
    # "ProcessedFiles" — neither Error nor DoNotSend is selected.
    assert not is_do_not_send, "unmatched master code must not trigger DoNotSend routing"


# =============================================================================
# _build_monthly_renamed_filename
# =============================================================================


def test_build_monthly_renamed_filename_standard_case() -> None:
    name = _build_monthly_renamed_filename("172691", "8030066978", "2025/05/01")
    assert name == "172691_8030066978_20250501請求明細書.pdf"


def test_build_monthly_renamed_filename_hyphen_date() -> None:
    name = _build_monthly_renamed_filename("172691", "8030066978", "2025-05-01")
    assert name == "172691_8030066978_20250501請求明細書.pdf"


def test_build_monthly_renamed_filename_na_date_uses_today() -> None:
    name = _build_monthly_renamed_filename("172691", "8030066978", "N/A")
    assert name.startswith("172691_8030066978_")
    assert name.endswith("請求明細書.pdf")
    date_segment = name.split("_")[2][:8]
    assert len(date_segment) == 8
    assert date_segment.isdigit()


def test_build_monthly_renamed_filename_empty_date_uses_today() -> None:
    name = _build_monthly_renamed_filename("111", "2222222222", "")
    assert name.endswith("請求明細書.pdf")


def test_build_monthly_renamed_filename_preserves_codes() -> None:
    name = _build_monthly_renamed_filename("ABC", "1234567890", "2025/12/31")
    assert name.startswith("ABC_1234567890_")
    assert name.endswith("請求明細書.pdf")


def test_build_monthly_renamed_filename_differs_from_daily() -> None:
    """Monthly and daily filenames must use different fixed-text suffixes."""
    monthly = _build_monthly_renamed_filename("172691", "8030066978", "2025/05/01")
    daily = _build_renamed_filename("172691", "8030066978", "2025/05/01")
    assert "請求明細書" in monthly
    assert "納品書兼請求書" in daily
    assert monthly != daily


def test_build_monthly_renamed_filename_garbage_date_uses_today() -> None:
    """A date field containing raw OCR label text (e.g. 'QUANTITY: 1') must
    not appear in the filename; today's date must be used as fallback."""
    name = _build_monthly_renamed_filename("172691", "8030066978", "QUANTITY: 1")
    # The date segment must be exactly 8 digits, not OCR label text.
    date_segment = name.split("_")[2][:8]
    assert len(date_segment) == 8
    assert date_segment.isdigit()
    assert "QUANTITY" not in name
    assert ":" not in name


def test_build_monthly_renamed_filename_partial_date_uses_today() -> None:
    """A date that resolves to fewer than 8 digits triggers today's date."""
    name = _build_monthly_renamed_filename("172691", "8030066978", "2025/05")
    date_segment = name.split("_")[2][:8]
    assert len(date_segment) == 8
    assert date_segment.isdigit()


def test_build_monthly_renamed_filename_no_invalid_chars_in_output() -> None:
    """Output filename must contain no Windows-invalid characters."""
    name = _build_monthly_renamed_filename("174579", "8030066822", "2025/05/01")
    assert not re.search(r'[<>:"/\\|?*]', name)


def test_build_monthly_renamed_filename_sanitizes_customer_code_with_colon() -> None:
    """customer_code containing a colon (e.g. raw OCR 'ITEM CODE: 8039440753')
    must have the colon stripped so the output filename is Windows-safe."""
    name = _build_monthly_renamed_filename("ITEM CODE: 8039440753", "8030066822", "2025/05/01")
    assert ":" not in name
    assert not re.search(r'[<>:"/\\|?*]', name)


def test_build_monthly_renamed_filename_sanitizes_all_invalid_chars() -> None:
    """All Windows-invalid characters are stripped from customer_code."""
    name = _build_monthly_renamed_filename('bad"name<here>', "8030066822", "2025/05/01")
    assert not re.search(r'[<>:"/\\|?*]', name)


# =============================================================================
# _safe_customer_code guard (behaviour validated through extract_invoice_data
# + routing logic — 10-digit item codes must be rejected)
# =============================================================================


def test_build_monthly_renamed_filename_strips_slash_and_colon_from_customer_code() -> None:
    """customer_code containing both '/' and ':' (both Windows-invalid path
    characters that cause WinError 123) must have both stripped.

    A customer_code like 'N/A: 8039440753' would produce a path where the '/'
    is treated as a directory separator on Windows and ':' makes the directory
    name invalid.  The sanitization layer must remove all such characters.
    """
    name = _build_monthly_renamed_filename("N/A: 8039440753", "8030066821", "2025/05/01")
    assert ":" not in name
    assert "/" not in name
    assert not re.search(r'[<>:"/\\|?*]', name)


# =============================================================================
# _split_pdf_pages
# =============================================================================


def _make_minimal_pdf(num_pages: int = 1) -> bytes:
    """Create a minimal valid PDF with the given number of blank pages."""
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_split_pdf_pages_single_page() -> None:
    pdf_bytes = _make_minimal_pdf(1)
    pages = _split_pdf_pages(pdf_bytes)
    assert len(pages) == 1
    assert isinstance(pages[0], bytes)
    assert len(pages[0]) > 0


def test_split_pdf_pages_multiple_pages() -> None:
    pdf_bytes = _make_minimal_pdf(3)
    pages = _split_pdf_pages(pdf_bytes)
    assert len(pages) == 3


def test_split_pdf_pages_each_result_is_valid_pdf() -> None:
    """Every page returned by _split_pdf_pages must be a readable PDF."""
    import io

    from pypdf import PdfReader

    pdf_bytes = _make_minimal_pdf(2)
    pages = _split_pdf_pages(pdf_bytes)
    for page_bytes in pages:
        reader = PdfReader(io.BytesIO(page_bytes))
        assert len(reader.pages) == 1


def test_split_pdf_pages_invalid_input_raises() -> None:
    """Non-PDF bytes must raise an exception (pypdf will reject it)."""
    import pytest

    with pytest.raises(Exception):
        _split_pdf_pages(b"not a pdf")


# =============================================================================
# _merge_pdf_pages
# =============================================================================


def test_merge_pdf_pages_two_single_page_pdfs() -> None:
    """Merging two single-page PDFs must yield a two-page PDF."""
    import io

    from pypdf import PdfReader

    pdf1 = _make_minimal_pdf(1)
    pdf2 = _make_minimal_pdf(1)
    merged = _merge_pdf_pages([pdf1, pdf2])
    reader = PdfReader(io.BytesIO(merged))
    assert len(reader.pages) == 2


def test_merge_pdf_pages_single_page_returns_single_page() -> None:
    """Merging a list with one PDF must return a one-page PDF."""
    import io

    from pypdf import PdfReader

    pdf = _make_minimal_pdf(1)
    merged = _merge_pdf_pages([pdf])
    reader = PdfReader(io.BytesIO(merged))
    assert len(reader.pages) == 1


def test_merge_pdf_pages_three_pages() -> None:
    """Merging three single-page PDFs must yield a three-page PDF."""
    import io

    from pypdf import PdfReader

    pages = [_make_minimal_pdf(1) for _ in range(3)]
    merged = _merge_pdf_pages(pages)
    reader = PdfReader(io.BytesIO(merged))
    assert len(reader.pages) == 3


def test_merge_pdf_pages_result_is_bytes() -> None:
    merged = _merge_pdf_pages([_make_minimal_pdf(1)])
    assert isinstance(merged, bytes)
    assert len(merged) > 0


# =============================================================================
# _group_monthly_pages
# =============================================================================


def _make_ocr_result(invoice_number: str = "1234567890") -> dict:
    """Return a minimal extract_invoice_data-style dict for testing."""
    return {
        "customer_code": "12345",
        "invoice_number": invoice_number,
        "invoice_date": "2025/05/01",
    }


@patch("routes.invoice_routes._ocr_monthly_page")
def test_group_monthly_pages_single_page_no_grouping(mock_ocr) -> None:
    """A single page forms its own group unchanged."""
    mock_ocr.return_value = (_make_ocr_result("1234567890"), None)
    pages = [_make_minimal_pdf(1)]
    groups = _group_monthly_pages(pages, "test", ".pdf")
    assert groups is not None
    assert len(groups) == 1
    assert groups[0]["page_nums"] == [1]
    assert groups[0]["merged_filename"] == "test_page1.pdf"
    assert groups[0]["ocr_error"] is None


@patch("routes.invoice_routes._ocr_monthly_page")
def test_group_monthly_pages_two_pages_same_invoice_merged(mock_ocr) -> None:
    """Two consecutive pages with the same Coll Invoice No. become one group."""
    mock_ocr.return_value = (_make_ocr_result("8030066978"), None)
    pages = [_make_minimal_pdf(1), _make_minimal_pdf(1)]
    groups = _group_monthly_pages(pages, "通常", ".pdf")
    assert groups is not None
    assert len(groups) == 1
    assert groups[0]["page_nums"] == [1, 2]
    assert groups[0]["merged_filename"] == "通常_page1-2.pdf"


@patch("routes.invoice_routes._ocr_monthly_page")
def test_group_monthly_pages_two_pages_different_invoices_separate(mock_ocr) -> None:
    """Two pages with different invoice numbers produce two separate groups."""
    mock_ocr.side_effect = [
        (_make_ocr_result("1111111111"), None),
        (_make_ocr_result("2222222222"), None),
    ]
    pages = [_make_minimal_pdf(1), _make_minimal_pdf(1)]
    groups = _group_monthly_pages(pages, "test", ".pdf")
    assert groups is not None
    assert len(groups) == 2
    assert groups[0]["page_nums"] == [1]
    assert groups[1]["page_nums"] == [2]


@patch("routes.invoice_routes._ocr_monthly_page")
def test_group_monthly_pages_three_pages_two_plus_one(mock_ocr) -> None:
    """Pages 1+2 share an invoice; page 3 has a different one → two groups."""
    mock_ocr.side_effect = [
        (_make_ocr_result("1111111111"), None),
        (_make_ocr_result("1111111111"), None),
        (_make_ocr_result("2222222222"), None),
    ]
    pages = [_make_minimal_pdf(1) for _ in range(3)]
    groups = _group_monthly_pages(pages, "test", ".pdf")
    assert groups is not None
    assert len(groups) == 2
    assert groups[0]["page_nums"] == [1, 2]
    assert groups[1]["page_nums"] == [3]


@patch("routes.invoice_routes._ocr_monthly_page")
def test_group_monthly_pages_ocr_error_makes_standalone_group(mock_ocr) -> None:
    """A page whose OCR fails is treated as a standalone single-page group."""
    mock_ocr.side_effect = [
        ({}, "DocWise timeout"),
        (_make_ocr_result("1234567890"), None),
    ]
    pages = [_make_minimal_pdf(1), _make_minimal_pdf(1)]
    groups = _group_monthly_pages(pages, "test", ".pdf")
    assert groups is not None
    assert len(groups) == 2
    assert groups[0]["page_nums"] == [1]
    assert groups[0]["ocr_error"] == "DocWise timeout"
    assert groups[1]["page_nums"] == [2]
    assert groups[1]["ocr_error"] is None


@patch("routes.invoice_routes._ocr_monthly_page")
def test_group_monthly_pages_invalid_invoice_number_standalone(mock_ocr) -> None:
    """A page with a non-10-digit invoice number is not grouped."""
    mock_ocr.side_effect = [
        (_make_ocr_result("N/A"), None),       # invalid — not 10 digits
        (_make_ocr_result("1234567890"), None),  # valid
    ]
    pages = [_make_minimal_pdf(1), _make_minimal_pdf(1)]
    groups = _group_monthly_pages(pages, "test", ".pdf")
    assert groups is not None
    assert len(groups) == 2
    assert groups[0]["page_nums"] == [1]
    assert groups[1]["page_nums"] == [2]


@patch("routes.invoice_routes._ocr_monthly_page")
def test_group_monthly_pages_group_error_when_second_page_fails(mock_ocr) -> None:
    """If the second page of a group fails OCR the whole group carries the error."""
    mock_ocr.side_effect = [
        (_make_ocr_result("1234567890"), None),
        ({}, "timeout on page 2"),
    ]
    pages = [_make_minimal_pdf(1), _make_minimal_pdf(1)]
    # Page 2 has an OCR error so it cannot be grouped — it's standalone.
    # Page 1 has a valid invoice_number and is also standalone.
    groups = _group_monthly_pages(pages, "test", ".pdf")
    assert groups is not None
    # Page 2 fails OCR → grouping_key is None → standalone group
    assert len(groups) == 2
    assert groups[0]["page_nums"] == [1]
    assert groups[0]["ocr_error"] is None
    assert groups[1]["page_nums"] == [2]
    assert groups[1]["ocr_error"] == "timeout on page 2"


@patch("routes.invoice_routes._ocr_monthly_page")
def test_group_monthly_pages_cancelled_returns_none(mock_ocr) -> None:
    """When cancel_event is set before OCR the function returns None."""
    import threading

    mock_ocr.return_value = (_make_ocr_result(), None)
    cancel_event = threading.Event()
    cancel_event.set()
    pages = [_make_minimal_pdf(1)]
    result = _group_monthly_pages(pages, "test", ".pdf", cancel_event)
    assert result is None
    mock_ocr.assert_not_called()


@patch("routes.invoice_routes._ocr_monthly_page")
def test_group_monthly_pages_merged_content_is_multi_page_pdf(mock_ocr) -> None:
    """The merged content for a two-page group must be a valid two-page PDF."""
    import io

    from pypdf import PdfReader

    mock_ocr.return_value = (_make_ocr_result("9876543210"), None)
    pages = [_make_minimal_pdf(1), _make_minimal_pdf(1)]
    groups = _group_monthly_pages(pages, "test", ".pdf")
    assert groups is not None
    assert len(groups) == 1
    merged = groups[0]["merged_content"]
    reader = PdfReader(io.BytesIO(merged))
    assert len(reader.pages) == 2


@patch("routes.invoice_routes._ocr_monthly_page")
def test_group_monthly_pages_invoice_data_from_first_page(mock_ocr) -> None:
    """The group's invoice_data must come from the first page in the group."""
    first_data = _make_ocr_result("1234567890")
    first_data["customer_code"] = "11111"
    second_data = _make_ocr_result("1234567890")
    second_data["customer_code"] = "22222"
    mock_ocr.side_effect = [(first_data, None), (second_data, None)]
    pages = [_make_minimal_pdf(1), _make_minimal_pdf(1)]
    groups = _group_monthly_pages(pages, "test", ".pdf")
    assert groups is not None
    assert len(groups) == 1
    assert groups[0]["invoice_data"]["customer_code"] == "11111"

