"""
Japan OCR Tool - Invoice Routes Helper Tests

Unit tests for the pure helper functions in routes.invoice_routes:
filename construction, folder path building, and the master-table lookup.

Author: SHIRIN MIRZI M K
"""

import pytest
from unittest.mock import MagicMock, patch

from routes.invoice_routes import (
    _build_execution_folder,
    _build_renamed_filename,
    _build_upload_folder,
    _lookup_master,
    _resolve_routing,
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

def _make_db_mock(row):
    """Return a mock get_db_connection context manager that yields *row* from fetchone."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = row

    mock_cursor_ctx = MagicMock()
    mock_cursor_ctx.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor_ctx.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor_ctx
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    return mock_conn


def test_lookup_master_not_found_returns_original_code() -> None:
    """Customer code absent from the master table → original code, not DoNotSend."""
    with patch("routes.invoice_routes.get_db_connection", return_value=_make_db_mock(None)):
        effective_code, is_do_not_send = _lookup_master("12345", "daily")
    assert effective_code == "12345"
    assert is_do_not_send is False


def test_resolve_routing_not_in_master_routes_to_processed_files_via_lookup() -> None:
    """When master lookup returns no row, _resolve_routing places the file in ProcessedFiles."""
    with patch("routes.invoice_routes.get_db_connection", return_value=_make_db_mock(None)):
        invoice_data = {"customer_code": "12345", "invoice_number": "INV001", "invoice_date": "2025/04/01"}
        folder, renamed = _resolve_routing(invoice_data, "daily", None)
    assert folder == "ProcessedFiles"
    assert renamed == "12345_INV001_20250401納品書兼請求書.pdf"


def test_lookup_master_found_numeric_destination_uses_destination_cd() -> None:
    """Master entry with numeric destination_cd → destination_cd as prefix, ProcessedFiles."""
    row = {"destination_cd": "789012"}
    with patch("routes.invoice_routes.get_db_connection", return_value=_make_db_mock(row)):
        effective_code, is_do_not_send = _lookup_master("12345", "daily")
    assert effective_code == "789012"
    assert is_do_not_send is False


def test_lookup_master_found_non_numeric_destination_sets_do_not_send() -> None:
    """Master entry with non-numeric destination_cd → original code, DoNotSend."""
    row = {"destination_cd": "送付無し"}
    with patch("routes.invoice_routes.get_db_connection", return_value=_make_db_mock(row)):
        effective_code, is_do_not_send = _lookup_master("12345", "daily")
    assert effective_code == "12345"
    assert is_do_not_send is True


def test_lookup_master_found_empty_destination_cd_falls_back() -> None:
    """Master row with empty destination_cd → original code, not DoNotSend."""
    row = {"destination_cd": ""}
    with patch("routes.invoice_routes.get_db_connection", return_value=_make_db_mock(row)):
        effective_code, is_do_not_send = _lookup_master("12345", "daily")
    assert effective_code == "12345"
    assert is_do_not_send is False


def test_lookup_master_db_error_returns_original_code() -> None:
    """DB connection failure → original code returned, not DoNotSend."""
    with patch("routes.invoice_routes.get_db_connection", side_effect=RuntimeError("db down")):
        effective_code, is_do_not_send = _lookup_master("12345", "daily")
    assert effective_code == "12345"
    assert is_do_not_send is False


def test_lookup_master_unknown_invoice_type_returns_original_code() -> None:
    """Unknown invoice type skips the DB call and returns the original code."""
    effective_code, is_do_not_send = _lookup_master("12345", "unknown")
    assert effective_code == "12345"
    assert is_do_not_send is False


# =============================================================================
# _resolve_routing
# =============================================================================

def test_resolve_routing_ocr_error_routes_to_error_folder() -> None:
    folder, renamed = _resolve_routing({}, "daily", "OCR failed")
    assert folder == "Error"
    assert renamed is None


def test_resolve_routing_missing_customer_code_routes_to_error() -> None:
    invoice_data = {"customer_code": "N/A", "invoice_number": "INV001", "invoice_date": "2025/04/01"}
    folder, renamed = _resolve_routing(invoice_data, "daily", None)
    assert folder == "Error"
    assert renamed is None


def test_resolve_routing_missing_invoice_number_routes_to_error() -> None:
    invoice_data = {"customer_code": "12345", "invoice_number": "N/A", "invoice_date": "2025/04/01"}
    folder, renamed = _resolve_routing(invoice_data, "daily", None)
    assert folder == "Error"
    assert renamed is None


def test_resolve_routing_not_in_master_routes_to_processed_files() -> None:
    """Core requirement: customer code not in master → ProcessedFiles, original code in filename."""
    with patch("routes.invoice_routes.get_db_connection", return_value=_make_db_mock(None)):
        invoice_data = {"customer_code": "99999", "invoice_number": "8039444166", "invoice_date": "2025/04/01"}
        folder, renamed = _resolve_routing(invoice_data, "daily", None)
    assert folder == "ProcessedFiles"
    assert renamed is not None
    assert renamed.startswith("99999_")


def test_resolve_routing_in_master_numeric_routes_to_processed_files() -> None:
    """Master match with numeric destination_cd → ProcessedFiles with destination_cd prefix."""
    row = {"destination_cd": "172865"}
    with patch("routes.invoice_routes.get_db_connection", return_value=_make_db_mock(row)):
        invoice_data = {"customer_code": "12345", "invoice_number": "8039444166", "invoice_date": "2025/04/01"}
        folder, renamed = _resolve_routing(invoice_data, "daily", None)
    assert folder == "ProcessedFiles"
    assert renamed is not None
    assert renamed.startswith("172865_")


def test_resolve_routing_in_master_do_not_send_routes_to_do_not_send_folder() -> None:
    """Non-numeric destination_cd → DoNotSend folder, original customer_code in filename."""
    row = {"destination_cd": "破棄"}
    with patch("routes.invoice_routes.get_db_connection", return_value=_make_db_mock(row)):
        invoice_data = {"customer_code": "12345", "invoice_number": "8039444166", "invoice_date": "2025/04/01"}
        folder, renamed = _resolve_routing(invoice_data, "daily", None)
    assert folder == "DoNotSend"
    assert renamed is not None
    assert renamed.startswith("12345_")


def test_resolve_routing_monthly_type_skips_rename() -> None:
    """Monthly invoices are not renamed and always go to ProcessedFiles."""
    invoice_data = {"customer_code": "12345", "invoice_number": "INV001"}
    folder, renamed = _resolve_routing(invoice_data, "monthly", None)
    assert folder == "ProcessedFiles"
    assert renamed is None
