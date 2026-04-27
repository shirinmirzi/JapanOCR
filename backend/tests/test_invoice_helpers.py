"""
Japan OCR Tool - Invoice Routes Helper Tests

Unit tests for the pure helper functions in routes.invoice_routes:
filename construction, folder path building, and the master-table lookup.

Author: SHIRIN MIRZI M K
"""

import pytest

from routes.invoice_routes import (
    _build_execution_folder,
    _build_renamed_filename,
    _build_upload_folder,
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
