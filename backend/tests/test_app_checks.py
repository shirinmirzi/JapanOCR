import csv
import io

from fastapi.testclient import TestClient

import main
from routes.auth_routes import compute_initials
from routes.config_routes import _parse_csv, _parse_excel, _validate_rows


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
