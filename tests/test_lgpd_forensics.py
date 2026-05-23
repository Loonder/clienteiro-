from datetime import date

from services.lgpd_service import LGPDService
from tests.conftest import MockConn, MockCursor


def test_create_request_rejects_invalid_type():
    result = LGPDService.create_request(
        {"request_type": "hack", "requester_name": "A", "requester_email": "a@a.com"},
        ip="1.1.1.1",
    )
    assert result["ok"] is False
    assert "invalido" in result["error"].lower()


def test_create_request_requires_contact():
    result = LGPDService.create_request(
        {"request_type": "acesso", "requester_name": "A", "requester_email": "", "requester_phone": ""},
        ip="1.1.1.1",
    )
    assert result["ok"] is False
    assert "telefone ou email" in result["error"].lower()


def test_create_request_persists_protocol(monkeypatch):
    cursor = MockCursor()
    conn = MockConn(cursor)
    monkeypatch.setattr("services.lgpd_service.get_db_connection", lambda: conn)
    monkeypatch.setattr("services.lgpd_service.LGPDService._build_protocol", lambda: "LGPD-20260328-ABCDEF12")

    result = LGPDService.create_request(
        {
            "request_type": "acesso",
            "requester_name": "Maria",
            "requester_phone": "11999999999",
            "requester_email": "",
            "message": "Quero meus dados",
        },
        ip="  10.0.0.7  ",
    )

    assert result == {"ok": True, "protocol": "LGPD-20260328-ABCDEF12"}
    assert conn.committed is True
    assert conn.closed is True
    assert any("INSERT INTO lgpd_requests" in sql for sql, _ in cursor.executed)
    _, params = cursor.executed[0]
    assert params[0] == "LGPD-20260328-ABCDEF12"
    assert params[-1] == "10.0.0.7"


def test_list_requests_clamps_limit(monkeypatch):
    cursor = MockCursor(fetchall_queue=[[{"id": 1, "protocol": "P"}]])
    conn = MockConn(cursor)
    monkeypatch.setattr("services.lgpd_service.get_db_connection", lambda: conn)

    result = LGPDService.list_requests(limit=9999)
    assert result["ok"] is True
    assert result["requests"][0]["id"] == 1
    sql, params = cursor.executed[0]
    assert "LIMIT %s" in sql
    assert params == (500,)


def test_update_request_status_rejects_invalid_status():
    result = LGPDService.update_request_status(1, "xpto", handled_by=1)
    assert result["ok"] is False
    assert "status invalido" in result["error"].lower()


def test_update_request_status_not_found(monkeypatch):
    cursor = MockCursor(fetchone_queue=[None])
    conn = MockConn(cursor)
    monkeypatch.setattr("services.lgpd_service.get_db_connection", lambda: conn)

    result = LGPDService.update_request_status(22, "concluido", handled_by=8)
    assert result["ok"] is False
    assert "nao encontrada" in result["error"].lower()
    assert conn.committed is True


def test_update_request_status_success(monkeypatch):
    cursor = MockCursor(fetchone_queue=[{"id": 22}])
    conn = MockConn(cursor)
    monkeypatch.setattr("services.lgpd_service.get_db_connection", lambda: conn)

    result = LGPDService.update_request_status(22, "concluido", handled_by=8)
    assert result == {"ok": True}


def test_retention_days_bounds(monkeypatch):
    monkeypatch.setenv("LEAD_RETENTION_DAYS", "10")
    assert LGPDService.retention_days() == 30
    monkeypatch.setenv("LEAD_RETENTION_DAYS", "99999")
    assert LGPDService.retention_days() == 1825
    monkeypatch.setenv("LEAD_RETENTION_DAYS", "180")
    assert LGPDService.retention_days() == 180


def test_compute_retention_until(monkeypatch):
    monkeypatch.setenv("LEAD_RETENTION_DAYS", "180")
    result = LGPDService.compute_retention_until()
    assert isinstance(result, date)


def test_run_retention_cleanup_returns_count(monkeypatch):
    cursor = MockCursor(fetchall_queue=[[{"id": 1}, {"id": 2}]])
    conn = MockConn(cursor)
    monkeypatch.setattr("services.lgpd_service.get_db_connection", lambda: conn)
    monkeypatch.setattr("services.lgpd_service.LGPDService.retention_days", lambda: 180)

    result = LGPDService.run_retention_cleanup()

    assert result == {"ok": True, "anonymized_count": 2}
    assert conn.committed is True
    assert len(cursor.executed) == 2
    assert "retention_until IS NULL" in cursor.executed[0][0]
    assert "SET user_name='ANONYMIZED'" in cursor.executed[1][0]
