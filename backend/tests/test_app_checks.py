from fastapi.testclient import TestClient

import main
from routes.auth_routes import compute_initials


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
