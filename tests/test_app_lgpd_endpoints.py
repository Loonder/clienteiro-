import importlib
import sys

import pytest

from tests.conftest import MockConn, MockCursor


@pytest.fixture
def app_module(monkeypatch):
    import core.auth as auth
    import core.db_manager as db_manager

    init_conn = MockConn(MockCursor())
    monkeypatch.setattr(db_manager, "init_postgres_db", lambda: None)
    monkeypatch.setattr(db_manager, "get_db_connection", lambda: init_conn)
    monkeypatch.setattr(auth, "seed_default_gestor", lambda conn: None)

    if "app" in sys.modules:
        del sys.modules["app"]
    mod = importlib.import_module("app")
    mod.app.config["TESTING"] = True
    mod._rate_store.clear()
    return mod


def _login_as(client, user_id=1, nivel="diretor", nome="Admin"):
    with client.session_transaction() as sess:
        sess["gestor_id"] = user_id
        sess["nivel_acesso"] = nivel
        sess["gestor_nome"] = nome


def test_lgpd_request_endpoint_success(monkeypatch, app_module):
    monkeypatch.setattr(app_module.LGPDService, "create_request", lambda payload, ip: {"ok": True, "protocol": "LGPD-TEST"})
    client = app_module.app.test_client()

    resp = client.post("/api/lgpd/request", json={"request_type": "acesso", "requester_name": "Ana", "requester_email": "ana@x.com"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["protocol"] == "LGPD-TEST"


def test_lgpd_request_endpoint_validation_error(monkeypatch, app_module):
    monkeypatch.setattr(app_module.LGPDService, "create_request", lambda payload, ip: {"ok": False, "error": "invalid"})
    client = app_module.app.test_client()

    resp = client.post("/api/lgpd/request", json={"request_type": "x"})
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_admin_lgpd_requests_requires_auth(app_module):
    client = app_module.app.test_client()
    resp = client.get("/admin/api/lgpd/requests")
    assert resp.status_code == 302
    assert "/login" in resp.location


def test_admin_lgpd_requests_requires_director(app_module):
    client = app_module.app.test_client()
    _login_as(client, nivel="consultor")
    resp = client.get("/admin/api/lgpd/requests")
    assert resp.status_code == 403


def test_admin_lgpd_requests_director_success(monkeypatch, app_module):
    monkeypatch.setattr(app_module.LGPDService, "list_requests", lambda limit=200: {"ok": True, "requests": [{"id": 1}]})
    client = app_module.app.test_client()
    _login_as(client, nivel="diretor")

    resp = client.get("/admin/api/lgpd/requests?limit=10")
    assert resp.status_code == 200
    assert resp.get_json()["requests"][0]["id"] == 1


def test_admin_lgpd_update_status_logs_action(monkeypatch, app_module):
    actions = []
    monkeypatch.setattr(app_module.LGPDService, "update_request_status", lambda request_id, status, handled_by: {"ok": True})
    monkeypatch.setattr(app_module, "get_db", lambda: MockConn(MockCursor()))
    monkeypatch.setattr(app_module, "log_acao", lambda conn, acao, lead_id=None: actions.append((acao, lead_id)))

    client = app_module.app.test_client()
    _login_as(client, user_id=7, nivel="diretor")
    resp = client.post("/admin/api/lgpd/requests/9/status", json={"status": "concluido"})

    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert actions[0][0].startswith("lgpd_request_status:")
    assert actions[0][1] == 9


def test_admin_lgpd_run_retention_logs_action(monkeypatch, app_module):
    actions = []
    monkeypatch.setattr(app_module.LGPDService, "run_retention_cleanup", lambda: {"ok": True, "anonymized_count": 3})
    monkeypatch.setattr(app_module, "get_db", lambda: MockConn(MockCursor()))
    monkeypatch.setattr(app_module, "log_acao", lambda conn, acao, lead_id=None: actions.append((acao, lead_id)))

    client = app_module.app.test_client()
    _login_as(client, user_id=11, nivel="diretor")
    resp = client.post("/admin/api/lgpd/run_retention")

    assert resp.status_code == 200
    assert resp.get_json()["anonymized_count"] == 3
    assert actions[0][0] == "lgpd_retention_cleanup:3"
