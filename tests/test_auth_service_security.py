import unicodedata

from flask import session

from services.auth_service import AuthService
from tests.conftest import MockConn, MockCursor


def _norm(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def test_login_success_sets_session(monkeypatch, flask_app):
    cursor = MockCursor(fetchone_queue=[{"id": 5, "nome": "Diretor", "nivel_acesso": "diretor", "senha_hash": "hash"}])
    conn = MockConn(cursor)
    monkeypatch.setattr("services.auth_service.get_db_connection", lambda: conn)
    monkeypatch.setattr("services.auth_service.check_password", lambda raw, stored: True)

    with flask_app.test_request_context("/login"):
        ok, level = AuthService.login("diretor", "secret")
        assert ok is True
        assert level == "diretor"
        assert session["gestor_id"] == 5
        assert session["gestor_nome"] == "Diretor"
        assert session["nivel_acesso"] == "diretor"


def test_login_failure_does_not_set_session(monkeypatch, flask_app):
    cursor = MockCursor(fetchone_queue=[None])
    conn = MockConn(cursor)
    monkeypatch.setattr("services.auth_service.get_db_connection", lambda: conn)

    with flask_app.test_request_context("/login"):
        ok, level = AuthService.login("x", "y")
        assert ok is False
        assert level is None
        assert "gestor_id" not in session


def test_register_rejects_missing_required(flask_app):
    with flask_app.test_request_context("/register"):
        ok, msg = AuthService.register({"nome": "", "nome_usuario": "", "senha": ""}, is_diretor=False)
        assert ok is False
        assert "campos obrigatorios" in _norm(msg)


def test_register_rejects_duplicate_username(monkeypatch, flask_app):
    cursor = MockCursor(fetchone_queue=[{"id": 1}])
    conn = MockConn(cursor)
    monkeypatch.setattr("services.auth_service.get_db_connection", lambda: conn)

    with flask_app.test_request_context("/register"):
        ok, msg = AuthService.register(
            {"nome": "A", "nome_usuario": "dup", "senha": "123", "cargo": "c"},
            is_diretor=False,
        )
        assert ok is False
        assert "ja cadastrado" in _norm(msg)


def test_register_success_hashes_password(monkeypatch, flask_app):
    cursor = MockCursor(fetchone_queue=[None])
    conn = MockConn(cursor)
    monkeypatch.setattr("services.auth_service.get_db_connection", lambda: conn)
    monkeypatch.setattr("services.auth_service.hash_password", lambda raw: f"HASH::{raw}")

    with flask_app.test_request_context("/register"):
        ok, msg = AuthService.register(
            {"nome": "Novo", "nome_usuario": "novo", "senha": "abc", "cargo": "vendas"},
            is_diretor=True,
        )

    assert ok is True
    assert "sucesso" in msg.lower()
    assert conn.committed is True
    assert any("INSERT INTO gestores" in sql for sql, _ in cursor.executed)
    insert_sql, insert_params = cursor.executed[-1]
    assert "INSERT INTO gestores" in insert_sql
    assert insert_params[2] == "HASH::abc"
    assert insert_params[4] == "cliente"


def test_logout_clears_session(flask_app):
    with flask_app.test_request_context("/logout"):
        session["gestor_id"] = 99
        AuthService.logout()
        assert dict(session) == {}
