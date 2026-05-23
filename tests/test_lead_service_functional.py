from datetime import date

from services.lead_service import LeadService
from tests.conftest import MockConn, MockCursor


class _DummyExecutor:
    def __init__(self):
        self.calls = []

    def submit(self, fn, *args, **kwargs):
        self.calls.append((fn, args, kwargs))
        return None


def _base_form():
    return {
        "company_name": "Empresa A",
        "user_name": "Lider A",
        "nicho": "Dentista",
        "city": "Sao Paulo",
        "user_phone": "11999999999",
        "type_focus": "b2b",
        "can_call": True,
    }


def _base_session():
    return {"nivel_acesso": "consultor", "gestor_id": 2, "gestor_nome": "Consultor"}


def test_process_submission_requires_lgpd_consent(tmp_path):
    form = _base_form()
    form["can_call"] = False

    result = LeadService.process_submission(
        form_data=form,
        logo_file=None,
        session_data=_base_session(),
        app_config={"DATA_DIR": str(tmp_path / "data"), "REPORTS_DIR": str(tmp_path / "reports")},
    )
    assert result["ok"] is False
    assert "consentimento" in result["error"].lower()


def test_process_submission_blocks_client_limit(monkeypatch, tmp_path):
    cursor = MockCursor(fetchone_queue=[None, {"gen_count": 3}])
    conn = MockConn(cursor)
    monkeypatch.setattr("services.lead_service.get_db_connection", lambda: conn)

    form = _base_form()
    session_data = {"nivel_acesso": "cliente", "gestor_id": 9, "gestor_nome": "Cliente"}

    result = LeadService.process_submission(
        form_data=form,
        logo_file=None,
        session_data=session_data,
        app_config={"DATA_DIR": str(tmp_path / "data"), "REPORTS_DIR": str(tmp_path / "reports")},
    )

    assert result["ok"] is False
    assert result["limit_reached"] is True
    assert "limite" in result["error"].lower()


def test_process_submission_allows_pro_client_over_free_limit(monkeypatch, tmp_path):
    cache_conn = MockConn(MockCursor(fetchone_queue=[None]))
    limit_cursor = MockCursor(fetchone_queue=[{"gen_count": 9, "plano": "pro"}])
    limit_conn = MockConn(limit_cursor)
    insert_conn = MockConn(MockCursor())
    conns = [cache_conn, limit_conn, insert_conn]
    monkeypatch.setattr("services.lead_service.get_db_connection", lambda: conns.pop(0))
    monkeypatch.setattr("services.lead_service.LGPDService.compute_retention_until", lambda: date(2026, 12, 31))

    class DummyProcessor:
        def __init__(self, payload):
            self.payload = payload

        def process(self):
            return {"clienteiro_score": 88}

    class DummyReporter:
        def __init__(self, enriched, slug):
            self.enriched = enriched
            self.slug = slug

        def generate(self, pdf_path):
            return None

    monkeypatch.setattr("services.lead_service.BusinessProcessor", DummyProcessor)
    monkeypatch.setattr("services.lead_service.PDFReporter", DummyReporter)
    monkeypatch.setattr("services.lead_service.LeadService._executor", _DummyExecutor())

    result = LeadService.process_submission(
        form_data=_base_form(),
        logo_file=None,
        session_data={"nivel_acesso": "cliente", "gestor_id": 9, "gestor_nome": "Cliente"},
        app_config={"DATA_DIR": str(tmp_path / "data"), "REPORTS_DIR": str(tmp_path / "reports")},
    )

    assert result["ok"] is True
    assert any("UPDATE gestores SET gen_count" in sql for sql, _ in limit_cursor.executed)


def test_process_submission_success_persists_lgpd_fields(monkeypatch, tmp_path):
    insert_cursor = MockCursor()
    insert_conn = MockConn(insert_cursor)
    monkeypatch.setattr("services.lead_service.get_db_connection", lambda: insert_conn)
    monkeypatch.setattr("services.lead_service.LGPDService.compute_retention_until", lambda: date(2026, 12, 31))

    class DummyProcessor:
        def __init__(self, payload):
            self.payload = payload

        def process(self):
            return {"clienteiro_score": 88}

    generated = []

    class DummyReporter:
        def __init__(self, enriched, slug):
            self.enriched = enriched
            self.slug = slug

        def generate(self, pdf_path):
            generated.append(pdf_path)

    executor = _DummyExecutor()
    monkeypatch.setattr("services.lead_service.BusinessProcessor", DummyProcessor)
    monkeypatch.setattr("services.lead_service.PDFReporter", DummyReporter)
    monkeypatch.setattr("services.lead_service.LeadService._executor", executor)

    form = _base_form()
    form["_client_ip"] = "10.10.0.1"
    form["_consent_version"] = "2026-03-28"

    result = LeadService.process_submission(
        form_data=form,
        logo_file=None,
        session_data=_base_session(),
        app_config={"DATA_DIR": str(tmp_path / "data"), "REPORTS_DIR": str(tmp_path / "reports")},
    )

    assert result["ok"] is True
    assert result["pdf_url"].startswith("/download/Diagnostico_")
    assert insert_conn.committed is True
    assert generated, "PDF generation should be called"
    assert executor.calls, "WhatsApp async submit should be scheduled"

    insert_sql, insert_params = next(
        (sql, params) for sql, params in insert_cursor.executed
        if "INSERT INTO internal_leads" in sql
    )
    assert "INSERT INTO internal_leads" in insert_sql
    assert insert_params[7] == "10.10.0.1"
    assert insert_params[8] == "2026-03-28"
    assert insert_params[9] == "consent"
    assert str(insert_params[12]) == "2026-12-31"


def test_process_submission_handles_pdf_failure(monkeypatch, tmp_path):
    insert_cursor = MockCursor()
    insert_conn = MockConn(insert_cursor)
    monkeypatch.setattr("services.lead_service.get_db_connection", lambda: insert_conn)
    monkeypatch.setattr("services.lead_service.LGPDService.compute_retention_until", lambda: date(2026, 1, 1))

    class DummyProcessor:
        def __init__(self, payload):
            self.payload = payload

        def process(self):
            return {"clienteiro_score": 70}

    class FailingReporter:
        def __init__(self, enriched, slug):
            self.enriched = enriched
            self.slug = slug

        def generate(self, pdf_path):
            raise RuntimeError("pdf broken")

    monkeypatch.setattr("services.lead_service.BusinessProcessor", DummyProcessor)
    monkeypatch.setattr("services.lead_service.PDFReporter", FailingReporter)
    monkeypatch.setattr("services.lead_service.LeadService._executor", _DummyExecutor())

    result = LeadService.process_submission(
        form_data=_base_form(),
        logo_file=None,
        session_data=_base_session(),
        app_config={"DATA_DIR": str(tmp_path / "data"), "REPORTS_DIR": str(tmp_path / "reports")},
    )

    assert result["ok"] is False
    assert "pdf" in result["error"].lower()


def test_send_whatsapp_uses_saasbot_internal_secret(monkeypatch, tmp_path):
    called = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

    def fake_post(url, json, headers, timeout):
        called["url"] = url
        called["json"] = json
        called["headers"] = headers
        called["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("SAASBOT_INTERNAL_URL", "http://bot:3582")
    monkeypatch.setenv("SAASBOT_TENANT_ID", "clienteiro")
    monkeypatch.setenv("SAASBOT_API_SECRET", "my-secret-123")
    monkeypatch.setattr("services.lead_service.requests.post", fake_post)

    LeadService._send_whatsapp("11999999999", "Ana", "Empresa", str(tmp_path / "r.pdf"))

    assert called["url"] == "http://bot:3582/internal/checkleads/offer/clienteiro"
    assert called["headers"]["x-bot-secret"] == "my-secret-123"
    assert called["json"]["phone"] == "11999999999"
    assert called["timeout"] == 15


def test_clean_text_trims_and_limits():
    raw = "   " + ("x" * 200) + "   "
    result = LeadService._clean_text(raw, fallback="f", max_len=10)
    assert result == "x" * 10
