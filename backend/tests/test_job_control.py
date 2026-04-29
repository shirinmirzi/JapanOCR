"""
Japan OCR Tool - Job Control Tests

Unit tests for the cancel_job and mark_stale_jobs_interrupted functions
added to services.jobs to address the continuous background processing loop.

Author: SHIRIN MIRZI M K
"""

import services.jobs as jobs_service


# =============================================================================
# cancel_job
# =============================================================================


def test_cancel_job_returns_true_when_job_is_active(monkeypatch) -> None:
    """cancel_job must return True when the UPDATE matches a row (active job)."""

    monkeypatch.setattr(jobs_service, "execute_write", lambda sql, params: {"id": params[0]})

    result = jobs_service.cancel_job("job-uuid-1")

    assert result is True


def test_cancel_job_returns_false_when_no_row_updated(monkeypatch) -> None:
    """cancel_job must return False when execute_write returns None (already terminal)."""

    monkeypatch.setattr(jobs_service, "execute_write", lambda sql, params: None)

    result = jobs_service.cancel_job("job-uuid-2")

    assert result is False


def test_cancel_job_passes_correct_job_id(monkeypatch) -> None:
    """cancel_job must pass the supplied job_id as the first positional param."""

    captured = []

    def fake_write(sql, params):
        captured.append(params)
        return {"id": params[0]}

    monkeypatch.setattr(jobs_service, "execute_write", fake_write)

    jobs_service.cancel_job("target-job-id")

    assert len(captured) == 1
    assert captured[0][0] == "target-job-id"


def test_cancel_job_only_cancels_active_statuses(monkeypatch) -> None:
    """The SQL must restrict updates to 'queued' or 'processing' rows."""

    captured_sql = []

    def fake_write(sql, params):
        captured_sql.append(sql)
        return None

    monkeypatch.setattr(jobs_service, "execute_write", fake_write)

    jobs_service.cancel_job("some-job")

    assert len(captured_sql) == 1
    sql_lower = captured_sql[0].lower()
    assert "queued" in sql_lower
    assert "processing" in sql_lower


# =============================================================================
# mark_stale_jobs_interrupted
# =============================================================================


def test_mark_stale_jobs_interrupted_calls_execute_write(monkeypatch) -> None:
    """mark_stale_jobs_interrupted must issue exactly one UPDATE statement."""

    calls = []

    def fake_write(sql, params=None):
        calls.append(sql)
        return None

    monkeypatch.setattr(jobs_service, "execute_write", fake_write)

    jobs_service.mark_stale_jobs_interrupted()

    assert len(calls) == 1


def test_mark_stale_jobs_interrupted_targets_active_statuses(monkeypatch) -> None:
    """The UPDATE must target both 'processing' and 'queued' rows."""

    captured_sql = []

    def fake_write(sql, params=None):
        captured_sql.append(sql)
        return None

    monkeypatch.setattr(jobs_service, "execute_write", fake_write)

    jobs_service.mark_stale_jobs_interrupted()

    assert len(captured_sql) == 1
    sql_lower = captured_sql[0].lower()
    assert "processing" in sql_lower
    assert "queued" in sql_lower
    assert "interrupted" in sql_lower


def test_mark_stale_jobs_interrupted_sets_interrupted_status(monkeypatch) -> None:
    """The UPDATE must set status to 'interrupted'."""

    captured_sql = []

    def fake_write(sql, params=None):
        captured_sql.append(sql)
        return None

    monkeypatch.setattr(jobs_service, "execute_write", fake_write)

    jobs_service.mark_stale_jobs_interrupted()

    sql = captured_sql[0]
    assert "interrupted" in sql.lower()
