"""
Japan OCR Tool - Logging Client Tests

Unit tests for the log data-access functions in services.logging_client.
Uses monkeypatching to avoid a real database connection.

Author: SHIRIN MIRZI M K
"""

import pytest

from services import logging_client


# =============================================================================
# log_invoice_result
# =============================================================================


def test_log_invoice_result_calls_execute_write(monkeypatch) -> None:
    written = []

    def fake_write(sql, params):
        written.append(params)

    monkeypatch.setattr(logging_client, "execute_write", fake_write)

    logging_client.log_invoice_result(
        filename="invoice.pdf",
        status="success",
        message="OK",
        user_id="dev_user",
    )

    assert len(written) == 1
    params = written[0]
    assert params[0] == "invoice.pdf"
    assert params[1] == "success"


def test_log_invoice_result_suppresses_db_errors(monkeypatch) -> None:
    def bad_write(sql, params):
        raise RuntimeError("db down")

    monkeypatch.setattr(logging_client, "execute_write", bad_write)

    # Should not raise; errors are swallowed to protect the caller.
    logging_client.log_invoice_result(filename="x.pdf", status="error")


def test_log_invoice_result_merges_metadata_fields(monkeypatch) -> None:
    written = []

    def fake_write(sql, params):
        written.append(params)

    monkeypatch.setattr(logging_client, "execute_write", fake_write)

    logging_client.log_invoice_result(
        filename="inv.pdf",
        status="success",
        renamed_filename="renamed.pdf",
        folder_name="ProcessedFiles",
        execution_folder="20250430_143022",
        module="invoice",
    )

    import json
    metadata_str = written[0][4]
    meta = json.loads(metadata_str)
    assert meta["renamed_filename"] == "renamed.pdf"
    assert meta["folder_name"] == "ProcessedFiles"
    assert meta["execution_folder"] == "20250430_143022"
    assert meta["module"] == "invoice"


# =============================================================================
# log_processing_start
# =============================================================================


def test_log_processing_start_returns_id_on_success(monkeypatch) -> None:
    monkeypatch.setattr(logging_client, "execute_write", lambda sql, params: {"id": 42})

    result = logging_client.log_processing_start("invoice.pdf", user_id="u1")
    assert result == 42


def test_log_processing_start_returns_none_on_db_error(monkeypatch) -> None:
    def bad_write(sql, params):
        raise RuntimeError("db error")

    monkeypatch.setattr(logging_client, "execute_write", bad_write)

    result = logging_client.log_processing_start("invoice.pdf")
    assert result is None


# =============================================================================
# update_log_entry
# =============================================================================


def test_update_log_entry_does_nothing_for_none_id(monkeypatch) -> None:
    executed = []
    monkeypatch.setattr(logging_client, "execute_query", lambda s, p=None: executed.append(s) or [])
    monkeypatch.setattr(logging_client, "execute_write", lambda s, p=None: None)

    # Should return immediately without any DB calls.
    logging_client.update_log_entry(None, "success")
    assert executed == []


def test_update_log_entry_merges_existing_metadata(monkeypatch) -> None:
    import json

    existing_meta = {"execution_folder": "20250430_143022", "module": "invoice"}

    monkeypatch.setattr(
        logging_client,
        "execute_query",
        lambda sql, params=None: [{"metadata": existing_meta}],
    )

    updated = []

    def capture_write(sql, params):
        updated.append(params)

    monkeypatch.setattr(logging_client, "execute_write", capture_write)

    logging_client.update_log_entry(
        log_id=1,
        status="success",
        renamed_filename="new_name.pdf",
        folder_name="ProcessedFiles",
    )

    assert len(updated) == 1
    stored_meta = json.loads(updated[0][3])
    # Original fields are preserved.
    assert stored_meta["execution_folder"] == "20250430_143022"
    # New fields are added.
    assert stored_meta["renamed_filename"] == "new_name.pdf"
    assert stored_meta["folder_name"] == "ProcessedFiles"


def test_update_log_entry_suppresses_db_errors(monkeypatch) -> None:
    monkeypatch.setattr(logging_client, "execute_query", lambda s, p=None: (_ for _ in ()).throw(RuntimeError("db")))
    # Should not raise.
    logging_client.update_log_entry(log_id=1, status="error")


# =============================================================================
# get_timeout_diagnostics
# =============================================================================


def test_get_timeout_diagnostics_returns_zero_counts_when_no_rows(monkeypatch) -> None:
    monkeypatch.setattr(logging_client, "execute_query", lambda s, p=None: [])

    result = logging_client.get_timeout_diagnostics()
    assert result["timeout_count"] == 0
    assert result["error_count"] == 0
    assert result["success_count"] == 0
    assert result["total"] == 0
    assert result["last_entry"] is None


def test_get_timeout_diagnostics_returns_row_values(monkeypatch) -> None:
    fake_row = {
        "timeout_count": 2,
        "error_count": 3,
        "success_count": 10,
        "total": 15,
        "last_entry": "2025-04-30T12:00:00",
    }
    monkeypatch.setattr(logging_client, "execute_query", lambda s, p=None: [fake_row])

    result = logging_client.get_timeout_diagnostics()
    assert result["timeout_count"] == 2
    assert result["success_count"] == 10


# =============================================================================
# mark_stale_logs_interrupted
# =============================================================================


def test_mark_stale_logs_interrupted_issues_update(monkeypatch) -> None:
    """mark_stale_logs_interrupted must issue exactly one UPDATE statement."""
    calls = []

    def fake_write(sql, params=None):
        calls.append(sql)

    monkeypatch.setattr(logging_client, "execute_write", fake_write)

    logging_client.mark_stale_logs_interrupted()

    assert len(calls) == 1


def test_mark_stale_logs_interrupted_targets_processing_status(monkeypatch) -> None:
    """The UPDATE must target rows with status = 'processing'."""
    captured_sql = []

    def fake_write(sql, params=None):
        captured_sql.append(sql)

    monkeypatch.setattr(logging_client, "execute_write", fake_write)

    logging_client.mark_stale_logs_interrupted()

    sql_lower = captured_sql[0].lower()
    assert "processing" in sql_lower
    assert "interrupted" in sql_lower


def test_mark_stale_logs_interrupted_suppresses_db_errors(monkeypatch) -> None:
    """mark_stale_logs_interrupted must not raise when the DB write fails."""
    def bad_write(sql, params=None):
        raise RuntimeError("db down")

    monkeypatch.setattr(logging_client, "execute_write", bad_write)

    # Should not raise.
    logging_client.mark_stale_logs_interrupted()

