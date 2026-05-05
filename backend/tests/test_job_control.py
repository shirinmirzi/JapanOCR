"""
Japan OCR Tool - Job Control Tests

Unit tests for the cancel_job, mark_stale_jobs_interrupted, set_current_file,
and cancel event registry functions in services.jobs that address the
continuous background processing loop and live progress UI requirements.

Author: SHIRIN MIRZI M K
"""

import threading

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


# =============================================================================
# set_current_file
# =============================================================================


def test_set_current_file_issues_update(monkeypatch) -> None:
    """set_current_file must issue one UPDATE statement."""

    calls = []

    def fake_write(sql, params):
        calls.append((sql, params))
        return None

    monkeypatch.setattr(jobs_service, "execute_write", fake_write)

    jobs_service.set_current_file("job-123", "invoice_001.pdf")

    assert len(calls) == 1


def test_set_current_file_passes_filename_and_job_id(monkeypatch) -> None:
    """set_current_file must pass the filename and job_id to the DB write."""

    captured = []

    def fake_write(sql, params):
        captured.append(params)
        return None

    monkeypatch.setattr(jobs_service, "execute_write", fake_write)

    jobs_service.set_current_file("job-abc", "test_invoice.pdf")

    assert len(captured) == 1
    params = captured[0]
    assert "test_invoice.pdf" in params
    assert "job-abc" in params


def test_set_current_file_accepts_none_to_clear(monkeypatch) -> None:
    """set_current_file must accept None to clear the current file field."""

    captured = []

    def fake_write(sql, params):
        captured.append(params)
        return None

    monkeypatch.setattr(jobs_service, "execute_write", fake_write)

    jobs_service.set_current_file("job-xyz", None)

    assert len(captured) == 1
    assert captured[0][0] is None


def test_set_current_file_updates_correct_job(monkeypatch) -> None:
    """set_current_file must target the supplied job_id in the WHERE clause."""

    captured = []

    def fake_write(sql, params):
        captured.append(params)
        return None

    monkeypatch.setattr(jobs_service, "execute_write", fake_write)

    jobs_service.set_current_file("specific-job-id", "file.pdf")

    assert captured[0][-1] == "specific-job-id"


# =============================================================================
# cancel event registry
# =============================================================================


def test_register_job_cancel_event_returns_threading_event() -> None:
    """register_job_cancel_event must return an unset threading.Event."""
    event = jobs_service.register_job_cancel_event("reg-job-1")
    try:
        assert isinstance(event, threading.Event)
        assert not event.is_set()
    finally:
        jobs_service.unregister_job_cancel_event("reg-job-1")


def test_signal_job_cancelled_sets_registered_event() -> None:
    """signal_job_cancelled must set the event for the given job_id."""
    event = jobs_service.register_job_cancel_event("sig-job-1")
    try:
        jobs_service.signal_job_cancelled("sig-job-1")
        assert event.is_set()
    finally:
        jobs_service.unregister_job_cancel_event("sig-job-1")


def test_signal_job_cancelled_is_noop_for_unknown_job() -> None:
    """signal_job_cancelled must not raise when job_id is not registered."""
    jobs_service.signal_job_cancelled("nonexistent-job-id")


def test_signal_all_jobs_cancelled_sets_all_events() -> None:
    """signal_all_jobs_cancelled must set every registered event."""
    ev1 = jobs_service.register_job_cancel_event("all-job-1")
    ev2 = jobs_service.register_job_cancel_event("all-job-2")
    try:
        jobs_service.signal_all_jobs_cancelled()
        assert ev1.is_set()
        assert ev2.is_set()
    finally:
        jobs_service.unregister_job_cancel_event("all-job-1")
        jobs_service.unregister_job_cancel_event("all-job-2")


def test_unregister_job_cancel_event_removes_event() -> None:
    """After unregister, signal_job_cancelled must not set the removed event."""
    event = jobs_service.register_job_cancel_event("unreg-job-1")
    jobs_service.unregister_job_cancel_event("unreg-job-1")
    jobs_service.signal_job_cancelled("unreg-job-1")
    assert not event.is_set()


def test_unregister_job_cancel_event_is_noop_for_unknown_job() -> None:
    """unregister_job_cancel_event must not raise for an unknown job_id."""
    jobs_service.unregister_job_cancel_event("never-registered")


# =============================================================================
# cancel_job — updated behaviour (signals in-process event)
# =============================================================================


def test_cancel_job_signals_event_when_update_succeeds(monkeypatch) -> None:
    """cancel_job must set the cancel event when the DB update matches a row."""
    monkeypatch.setattr(jobs_service, "execute_write", lambda sql, params: {"id": params[0]})

    event = jobs_service.register_job_cancel_event("cancel-signal-job")
    try:
        jobs_service.cancel_job("cancel-signal-job")
        assert event.is_set()
    finally:
        jobs_service.unregister_job_cancel_event("cancel-signal-job")


def test_cancel_job_does_not_signal_event_when_update_fails(monkeypatch) -> None:
    """cancel_job must NOT set the cancel event when no row was updated."""
    monkeypatch.setattr(jobs_service, "execute_write", lambda sql, params: None)

    event = jobs_service.register_job_cancel_event("no-cancel-signal-job")
    try:
        jobs_service.cancel_job("no-cancel-signal-job")
        assert not event.is_set()
    finally:
        jobs_service.unregister_job_cancel_event("no-cancel-signal-job")


# =============================================================================
# mark_stale_jobs_interrupted — updated behaviour (signals all events)
# =============================================================================


def test_mark_stale_jobs_interrupted_signals_all_events(monkeypatch) -> None:
    """mark_stale_jobs_interrupted must signal all registered cancel events."""
    monkeypatch.setattr(jobs_service, "execute_write", lambda sql, params=None: None)

    ev1 = jobs_service.register_job_cancel_event("stale-job-a")
    ev2 = jobs_service.register_job_cancel_event("stale-job-b")
    try:
        jobs_service.mark_stale_jobs_interrupted()
        assert ev1.is_set()
        assert ev2.is_set()
    finally:
        jobs_service.unregister_job_cancel_event("stale-job-a")
        jobs_service.unregister_job_cancel_event("stale-job-b")
