from core.processor import BusinessProcessor
from tests.conftest import MockConn, MockCursor


def test_db_mode_can_fallback_to_live_scraping(monkeypatch):
    cursor = MockCursor(fetchall_queue=[[], [], []])
    conn = MockConn(cursor)
    monkeypatch.setattr("core.processor.get_db_connection", lambda: conn)
    monkeypatch.setenv("LEADS_SOURCE", "db")
    monkeypatch.setenv("LEADS_FALLBACK", "live")
    monkeypatch.setenv("ENABLE_LIVE_SCRAPING", "false")
    monkeypatch.setenv("LEADS_PER_REPORT", "3")

    class FakeMapsScraper:
        closed = False

        def __init__(self, headless=True):
            self.headless = headless

        def fetch_leads(self, nicho, city, max_leads):
            return [{
                "name": "Clinica Teste",
                "phone": "(11) 99999-9999",
                "rating": 4.8,
                "source": "https://maps.example/place/1",
            }]

        def close(self):
            FakeMapsScraper.closed = True

    monkeypatch.setattr("core.maps_scraper.MapsScraper", FakeMapsScraper)

    leads = BusinessProcessor({
        "nicho": "Odontologia",
        "city": "Sao Paulo",
        "type_focus": "b2b",
    })._fetch_strategic_leads()

    assert leads[0]["name"] == "Clinica Teste"
    assert FakeMapsScraper.closed is True
    assert conn.closed is True
