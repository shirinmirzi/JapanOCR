# Testing Guide

This document explains the test strategy, test structure, and how to run the test suite.

---

## Test Stack

| Tool | Version | Purpose |
|---|---|---|
| pytest | ≥8.0 | Test runner |
| pytest-asyncio | ≥0.23 | Async test support |
| FastAPI TestClient | bundled | Integration testing via HTTPX |
| openpyxl | ≥3.1 | Excel fixture generation in tests |

---

## Test Structure

All backend tests live in `backend/tests/`.

| File | Coverage area |
|---|---|
| `test_app_checks.py` | Application startup, health endpoint, config/master-upload helpers |
| `test_docwise_client.py` | OCR response parsing: `pick_response_text`, `_is_header_line`, `extract_invoice_data` |
| `test_entra_auth.py` | JWT decoding, user-profile extraction, auth middleware integration |
| `test_invoice_helpers.py` | Invoice route helpers: filename/folder construction |
| `test_logging_client.py` | Log insert, update, and diagnostic query helpers |

---

## Running Tests

```bash
# From the backend directory
cd backend

# Run the full suite
python -m pytest tests/ -v

# Run a single file
python -m pytest tests/test_docwise_client.py -v

# Run a specific test by name
python -m pytest tests/test_docwise_client.py::test_extract_invoice_data_parses_daily_pipe_line -v
```

---

## Design Principles

### Unit tests use monkeypatching, not a real database

Database calls (`execute_query`, `execute_write`) are replaced with lightweight
fakes so tests run without a PostgreSQL connection:

```python
def test_log_invoice_result_calls_execute_write(monkeypatch) -> None:
    written = []
    monkeypatch.setattr(logging_client, "execute_write", lambda s, p: written.append(p))
    logging_client.log_invoice_result(filename="invoice.pdf", status="success")
    assert len(written) == 1
```

### Integration tests use FastAPI TestClient

Tests that exercise full request/response cycles use `TestClient`:

```python
def test_health_endpoint_reports_connected_database(monkeypatch) -> None:
    monkeypatch.setattr(main, "execute_query", lambda _sql: [{"ok": 1}])
    with TestClient(main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
```

### Auth is bypassed via SKIP_AUTH

Tests that hit protected routes set `middleware.entra_auth.SKIP_AUTH = True`:

```python
monkeypatch.setattr("middleware.entra_auth.SKIP_AUTH", True)
```

---

## Adding New Tests

1. Create a new file in `backend/tests/` named `test_<area>.py`.
2. Add a module docstring following the comment standard.
3. Group tests under clearly named section comments (`# ===` separators).
4. Keep each test focused on a single behaviour.
5. Use descriptive test names that read as sentences:
   `test_extract_invoice_data_skips_header_row_for_daily`.

---

## Coverage Areas Not Yet Automated

The following areas rely on manual testing or real infrastructure and are out of scope
for the unit test suite:

- Azure Blob Storage upload / SAS URL generation (requires Azure credentials)
- DocWise API HTTP calls (external service; tested via mocked responses)
- MSAL / Entra ID token validation (requires a valid Azure tenant)
- PostgreSQL schema migrations (tested manually on first run)

---

Author: SHIRIN MIRZI M K
