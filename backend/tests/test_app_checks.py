import csv
import io

from fastapi.testclient import TestClient

import main
from routes.auth_routes import compute_initials
from routes.config_routes import _parse_csv, _parse_excel, _validate_rows
from routes.invoice_routes import _DO_NOT_SEND_VALUE, _lookup_daily_master


def test_compute_initials_handles_names() -> None:
    assert compute_initials('Jane Doe') == 'JD'
    assert compute_initials('Madonna') == 'M'
    assert compute_initials('') == '?'


def test_health_endpoint_reports_connected_database(monkeypatch) -> None:
    monkeypatch.setattr(main, 'execute_query', lambda _sql: [{'ok': 1}])

    with TestClient(main.app) as client:
        response = client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'database': 'connected'}


def test_health_endpoint_reports_database_issue(monkeypatch) -> None:
    def raise_db_error(_sql):
        raise RuntimeError('database unavailable')

    monkeypatch.setattr(main, 'execute_query', raise_db_error)

    with TestClient(main.app) as client:
        response = client.get('/health')

    assert response.status_code == 200
    assert response.json() == {
        'status': 'degraded',
        'database': 'error: database unavailable',
    }


# ── Config / master-upload helpers ──────────────────────────────────────────


def _make_csv_bytes(rows: list) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode('utf-8')


def _make_xlsx_bytes(rows: list) -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_csv_returns_rows() -> None:
    data = _make_csv_bytes([['Customer CD.', '送付先 CD.'], ['199621', '送付無し'], ['199622', '123']])
    rows = _parse_csv(data)
    assert len(rows) == 2
    assert rows[0]['customer_cd'] == '199621'
    assert rows[0]['destination_cd'] == '送付無し'
    assert rows[0]['source_row'] == 2
    assert rows[1]['customer_cd'] == '199622'
    assert rows[1]['destination_cd'] == '123'
    assert rows[1]['source_row'] == 3


def test_parse_csv_skips_blank_rows() -> None:
    data = _make_csv_bytes([['Customer CD.', '送付先 CD.'], ['199621', '123'], ['', ''], ['199622', '456']])
    rows = _parse_csv(data)
    assert len(rows) == 2


def test_parse_excel_returns_rows() -> None:
    data = _make_xlsx_bytes([['Customer CD.', '送付先 CD.'], ['199621', '破棄'], ['199622', '99']])
    rows = _parse_excel(data)
    assert len(rows) == 2
    assert rows[0]['customer_cd'] == '199621'
    assert rows[0]['destination_cd'] == '破棄'
    assert rows[0]['source_row'] == 2
    assert rows[1]['customer_cd'] == '199622'
    assert rows[1]['destination_cd'] == '99'
    assert rows[1]['source_row'] == 3


def test_parse_excel_skips_blank_rows() -> None:
    data = _make_xlsx_bytes([['Customer CD.', '送付先 CD.'], ['199621', '123'], [None, None], ['199622', '456']])
    rows = _parse_excel(data)
    assert len(rows) == 2


def test_validate_rows_splits_valid_and_invalid() -> None:
    rows = [
        {'customer_cd': '199621', 'destination_cd': '送付無し'},
        {'customer_cd': '', 'destination_cd': '123'},
        {'customer_cd': '199622', 'destination_cd': '破棄'},
    ]
    valid, invalid = _validate_rows(rows)
    assert len(valid) == 2
    assert len(invalid) == 1
    assert invalid[0]['reason'] == 'customer_cd is empty'
    assert valid[0]['row_number'] == 1
    assert valid[1]['row_number'] == 3


def test_master_upload_rejects_bad_master_type(monkeypatch) -> None:
    monkeypatch.setattr('middleware.entra_auth.SKIP_AUTH', True)

    csv_bytes = _make_csv_bytes([['199621', '123']])

    with TestClient(main.app) as client:
        response = client.post(
            '/api/config/master-upload',
            data={'master_type': 'invalid'},
            files={'file': ('test.csv', csv_bytes, 'text/csv')},
        )

    assert response.status_code == 400
    assert 'master_type' in response.json()['detail']


def test_master_upload_rejects_unsupported_file_type(monkeypatch) -> None:
    monkeypatch.setattr('middleware.entra_auth.SKIP_AUTH', True)

    with TestClient(main.app) as client:
        response = client.post(
            '/api/config/master-upload',
            data={'master_type': 'daily'},
            files={'file': ('test.txt', b'data', 'text/plain')},
        )

    assert response.status_code == 400
    assert 'Unsupported file type' in response.json()['detail']


def test_master_upload_csv_inserts_rows(monkeypatch) -> None:
    monkeypatch.setattr('middleware.entra_auth.SKIP_AUTH', True)

    inserted_rows = []

    class _FakeCursor:
        def __init__(self):
            self.description = None

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, params=None):
            pass

        def executemany(self, sql, rows):
            inserted_rows.extend(rows)

        def fetchall(self):
            return []

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def cursor(self):
            return _FakeCursor()

        def commit(self):
            pass

        def rollback(self):
            pass

    from contextlib import contextmanager

    @contextmanager
    def _fake_db():
        yield _FakeConn()

    monkeypatch.setattr('routes.config_routes.get_db_connection', _fake_db)

    csv_bytes = _make_csv_bytes([
        ['Customer CD.', '送付先 CD.'],
        ['199621', '送付無し'],
        ['199622', '123'],
        ['', 'skip-this'],
    ])

    with TestClient(main.app) as client:
        response = client.post(
            '/api/config/master-upload',
            data={'master_type': 'daily'},
            files={'file': ('master.csv', csv_bytes, 'text/csv')},
        )

    assert response.status_code == 200
    body = response.json()
    assert body['master_type'] == 'daily'
    assert body['inserted'] == 2
    assert body['skipped'] == 1
    assert len(body['invalid_rows']) == 1
    # Verify Japanese text was preserved; source row 2 is the first data row
    assert ('199621', '送付無し', 2) in inserted_rows


# ── Daily invoice routing ─────────────────────────────────────────────────────


def _make_fake_db_lookup(mapping):
    """Return a context-manager factory that mimics get_db_connection for
    _lookup_daily_master, using *mapping* as the in-memory master table."""
    from contextlib import contextmanager

    class _FakeCursor:
        def __init__(self):
            self.description = [('destination_cd',)]
            self._result = None

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def execute(self, sql, params=None):
            if mapping is not None and params:
                value = mapping.get(params[0])
                self._result = {'destination_cd': value} if value is not None else None
            else:
                self._result = None

        def fetchone(self):
            return self._result

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def cursor(self):
            return _FakeCursor()

        def commit(self):
            pass

        def rollback(self):
            pass

    @contextmanager
    def _fake_db():
        yield _FakeConn()

    return _fake_db


def test_do_not_send_value_is_correct_japanese() -> None:
    """The constant must match the Japanese value used in the master table."""
    assert _DO_NOT_SEND_VALUE == '送付無し、破棄'


def test_lookup_daily_master_returns_destination_cd(monkeypatch) -> None:
    monkeypatch.setattr(
        'routes.invoice_routes.get_db_connection',
        _make_fake_db_lookup({'199621': '送付無し、破棄'}),
    )
    assert _lookup_daily_master('199621') == '送付無し、破棄'


def test_lookup_daily_master_returns_none_when_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        'routes.invoice_routes.get_db_connection',
        _make_fake_db_lookup({}),
    )
    assert _lookup_daily_master('999999') is None


def test_lookup_daily_master_returns_none_on_db_error(monkeypatch) -> None:
    def _bad_db():
        raise RuntimeError('db is down')

    monkeypatch.setattr('routes.invoice_routes.get_db_connection', _bad_db)
    assert _lookup_daily_master('199621') is None


def _fake_invoice_upload_infra(monkeypatch, master_mapping):
    """Patch all external dependencies for the /api/invoices/upload endpoint."""
    monkeypatch.setattr('middleware.entra_auth.SKIP_AUTH', True)

    monkeypatch.setattr(
        'routes.invoice_routes.analyze_document',
        lambda *a, **kw: {},
    )
    monkeypatch.setattr(
        'routes.invoice_routes.extract_invoice_data',
        lambda *a, **kw: {
            'customer_code': '199621',
            'invoice_number': 'INV001',
            'invoice_date': '20260401',
        },
    )

    monkeypatch.setattr(
        'routes.invoice_routes.azure_storage_client.upload_file',
        lambda content, path: f'https://fake/{path}',
    )

    monkeypatch.setattr('routes.invoice_routes.log_processing_start', lambda *a, **kw: 1)
    monkeypatch.setattr('routes.invoice_routes.update_log_entry', lambda *a, **kw: None)
    monkeypatch.setattr('routes.invoice_routes.create_invoice', lambda **kw: {'id': 42})

    monkeypatch.setattr(
        'routes.invoice_routes.get_db_connection',
        _make_fake_db_lookup(master_mapping),
    )


def _minimal_pdf_bytes() -> bytes:
    """A minimal but valid PDF byte string for use in upload tests."""
    return b'%PDF-1.4 1 0 obj<</Type/Catalog>>endobj\n%%EOF'


def test_daily_upload_routes_to_processed_files_when_found(monkeypatch) -> None:
    _fake_invoice_upload_infra(monkeypatch, {'199621': '199621'})
    with TestClient(main.app) as client:
        response = client.post(
            '/api/invoices/upload',
            data={'invoice_type': 'daily'},
            files={'file': ('inv.pdf', _minimal_pdf_bytes(), 'application/pdf')},
        )
    assert response.status_code == 200
    body = response.json()
    assert body['output_folder'] == 'ProcessedFiles'
    assert body['renamed_filename'] is not None


def test_daily_upload_routes_to_do_not_send_when_mapped(monkeypatch) -> None:
    _fake_invoice_upload_infra(monkeypatch, {'199621': '送付無し、破棄'})
    with TestClient(main.app) as client:
        response = client.post(
            '/api/invoices/upload',
            data={'invoice_type': 'daily'},
            files={'file': ('inv.pdf', _minimal_pdf_bytes(), 'application/pdf')},
        )
    assert response.status_code == 200
    body = response.json()
    assert body['output_folder'] == 'DoNotSend'


def test_daily_upload_routes_to_error_when_customer_not_found(monkeypatch) -> None:
    _fake_invoice_upload_infra(monkeypatch, {})
    with TestClient(main.app) as client:
        response = client.post(
            '/api/invoices/upload',
            data={'invoice_type': 'daily'},
            files={'file': ('inv.pdf', _minimal_pdf_bytes(), 'application/pdf')},
        )
    assert response.status_code == 200
    body = response.json()
    assert body['output_folder'] == 'Error'
