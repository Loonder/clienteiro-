import time
import re
import os
import sys
from urllib.parse import urlparse, parse_qs, unquote

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("[Maps] ⚠️ Selenium/Webdriver-Manager não instalados.")


def _format_br_phone(raw: str) -> str:
    digits = re.sub(r'\D', '', str(raw or ''))
    if not digits:
        return ''
    if digits.startswith('55') and len(digits) in (12, 13):
        digits = digits[2:]
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return ''


def _extract_phone_candidates(text: str) -> list:
    blob = str(text or '')
    patterns = (
        r'(?:\+?55[\s\-.]*)?(?:\(?\d{2}\)?[\s\-.]*)?(?:9[\s\-.]*)?(?:\d[\s\-.]*){7}\d',
        r'\b(?:55)?\d{10,13}\b',
    )
    found = []
    for pattern in patterns:
        for match in re.findall(pattern, blob):
            fmt = _format_br_phone(match)
            if fmt and fmt not in found:
                found.append(fmt)
    return found


class MapsScraper:
    """
    Motor de Extração do Google Maps — Abordagem URL-First.

    ESTRATÉGIA ANTI-STALE:
    1. Fase 1: Coleta APENAS os hrefs dos cards via JavaScript puro (strings, nunca ficam stale).
    2. Fase 2: Navega para cada URL individualmente com driver.get().
       Na página de detalhe do lugar, o número aparece como <a href="tel:..."> — sempre.
    3. Nunca mantém referências DOM entre páginas.
    """

    _semaphore = None
    _active_drivers = set()

    def __init__(self, headless=True):
        self.headless = headless
        self._driver = None
        if MapsScraper._semaphore is None:
            import threading
            MapsScraper._semaphore = threading.Semaphore(2)

    @classmethod
    def close_active_drivers(cls):
        for drv in list(cls._active_drivers):
            try:
                drv.quit()
            except Exception:
                pass
            finally:
                cls._active_drivers.discard(drv)

    def _build_driver(self):
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--log-level=3")
        opts.add_argument("--disable-notifications")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--blink-settings=imagesEnabled=false")
        opts.add_argument("--disable-features=Translate,OptimizationHints,MediaRouter")
        opts.add_argument("--no-first-run")
        opts.add_argument("--no-default-browser-check")
        opts.add_argument("--mute-audio")
        opts.add_argument("--disable-software-rasterizer")
        opts.add_argument("--disable-background-networking")
        opts.add_argument("--disable-sync")
        opts.add_argument("--disable-default-apps")
        opts.add_argument("--disable-setuid-sandbox")
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
        MapsScraper._active_drivers.add(driver)
        self._driver = driver
        return driver

    def close(self):
        if not self._driver:
            return
        try:
            self._driver.quit()
            print("[Maps] Navegador encerrado com seguranca.")
        except Exception:
            pass
        finally:
            MapsScraper._active_drivers.discard(self._driver)
            self._driver = None

    @staticmethod
    def _should_stop(callback) -> bool:
        if not callback:
            return False
        try:
            return bool(callback())
        except Exception:
            return False

    def _sleep_interruptible(self, seconds: float, should_stop=None) -> bool:
        deadline = time.time() + max(0, float(seconds))
        while time.time() < deadline:
            if self._should_stop(should_stop):
                return True
            time.sleep(min(0.2, max(0, deadline - time.time())))
        return self._should_stop(should_stop)

    def _extract_phone_from_place_page(self, driver) -> str:
        """
        Extrai o telefone da página de detalhe do Google Maps.
        Na página de detalhe (<maps/place/...>), o número sempre aparece
        como <a href="tel:..."> — muito mais confiável que o painel lateral.
        """
        try:
            # Método 1 (mais confiável): <a href="tel:...">
            tel_links = driver.find_elements(By.CSS_SELECTOR, 'a[href^="tel:"]')
            for link in tel_links:
                href = (link.get_attribute('href') or '').replace('tel:', '').strip()
                fmt = _format_br_phone(href)
                if fmt:
                    return fmt

            # Método 2: aria-label de botão com o número
            btns = driver.find_elements(
                By.CSS_SELECTOR,
                '[data-item-id^="phone"], [aria-label*="Telefone"], [aria-label*="telefone"]'
            )
            for btn in btns:
                label = btn.get_attribute('aria-label') or ''
                candidates = _extract_phone_candidates(label)
                if candidates:
                    return candidates[0]

            # Método 3: varredura do texto da seção de contato
            try:
                page_text = driver.find_element(By.TAG_NAME, 'body').text
                candidates = _extract_phone_candidates(page_text)
                if candidates:
                    return candidates[0]
            except Exception:
                pass

        except Exception as e:
            print(f"[Maps] ⚠️ Erro ao extrair telefone: {e}")

        return ''

    def fetch_leads(self, nicho: str, city: str, max_leads: int = 15, on_lead=None, should_stop=None) -> list:
        leads = []
        query = f"{nicho} {city}"
        print(f"[Maps] 🚀 Iniciando scraper para: '{query}'...")
        initial_wait = float(os.getenv('MAPS_INITIAL_WAIT_SECONDS', '1.8'))
        scroll_rounds = max(0, int(os.getenv('MAPS_SCROLL_ROUNDS', '3')))
        scroll_wait = float(os.getenv('MAPS_SCROLL_WAIT_SECONDS', '0.4'))
        detail_wait = float(os.getenv('MAPS_DETAIL_WAIT_SECONDS', '1.0'))

        with MapsScraper._semaphore:
            driver = None
            try:
                driver = self._build_driver()
                if self._should_stop(should_stop):
                    return leads

                # ── FASE 1: Coleta apenas URLs (strings — jamais ficam stale) ──────
                url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
                driver.get(url)
                if self._sleep_interruptible(initial_wait, should_stop):
                    return leads

                # Scroll para carregar mais resultados na lista
                for _ in range(scroll_rounds):
                    if self._should_stop(should_stop):
                        return leads
                    try:
                        driver.execute_script('''
                            const feed = document.querySelector('div[role="feed"]');
                            if (feed) { feed.scrollTop = feed.scrollHeight; }
                            window.scrollBy(0, 800);
                        ''')
                        if self._sleep_interruptible(scroll_wait, should_stop):
                            return leads
                    except Exception:
                        pass

                # Extrai hrefs e labels via JS — resultado é lista de dicts Python (sem referência DOM)
                card_data = driver.execute_script('''
                    const anchors = Array.from(document.querySelectorAll("a.hfpxzc"));
                    return anchors.map(a => ({
                        href: a.href || "",
                        label: a.getAttribute("aria-label") || ""
                    })).filter(d => d.href && d.href.includes("/maps/place/"));
                ''')

                print(f"[Maps] ✅ {len(card_data)} URLs de lugares coletados. Iniciando extração...")

                seen_labels = set()

                # ── FASE 2: Navega para cada URL individualmente ──────────────────
                for idx, item in enumerate(card_data):
                    if self._should_stop(should_stop):
                        print("[Maps] Parada solicitada. Encerrando extracao atual.")
                        break
                    if len(leads) >= max_leads:
                        break

                    href = item.get('href', '')
                    label = item.get('label', '').strip()

                    if not href or not label:
                        continue
                    if label in seen_labels:
                        continue
                    seen_labels.add(label)

                    name = label[:55] if label else f"Lugar #{idx+1}"

                    try:
                        # Verifica parada ANTES de abrir nova página (evita Connection refused em cascata)
                        if self._should_stop(should_stop) or self._driver is None:
                            print("[Maps] Parada detectada antes de navegar. Abortando fila.")
                            break

                        # Navega diretamente para a página do lugar
                        driver.get(href)
                        if self._sleep_interruptible(detail_wait, should_stop):
                            break

                        # Extrai telefone real
                        phone = self._extract_phone_from_place_page(driver)

                        # Extrai rating do aria-label da estrela ou span dedicado
                        rating = 4.2
                        try:
                            rating_els = driver.find_elements(
                                By.CSS_SELECTOR,
                                'span.ceNzKf, [aria-label*="estrela"], [aria-label*=" star"]'
                            )
                            for el in rating_els:
                                aria = el.get_attribute('aria-label') or ''
                                m = re.search(r'(\d[.,]\d)', aria)
                                if m:
                                    rating = float(m.group(1).replace(',', '.'))
                                    break
                        except Exception:
                            pass

                        lead = {
                            'name': name,
                            'phone': phone if phone else 'Ver na Web',
                            'rating': rating,
                            'source': href
                        }
                        leads.append(lead)
                        status = f"✅ {phone}" if phone else "❌ Sem telefone"
                        print(f"[Maps] [{len(leads)}] {name[:40]} → {status}", flush=True)
                        if on_lead:
                            try:
                                on_lead(dict(lead))
                            except Exception as callback_err:
                                print(f"[Maps] Callback ao vivo falhou: {callback_err}", flush=True)

                    except Exception as e:
                        if self._should_stop(should_stop) or self._driver is None:
                            print("[Maps] Parada solicitada durante navegacao. Encerrando sem continuar a fila.")
                            break
                        print(f"[Maps] ⚠️ Erro no item #{idx} ({name[:30]}): {repr(e)}")
                        continue

            except Exception as e:
                print(f"[Maps] ⚠️ Erro geral: {repr(e)}")
            finally:
                self.close()
                if False and driver:
                    try:
                        driver.quit()
                        print("[Maps] 🛑 Navegador encerrado com segurança.")
                    except Exception:
                        pass
                    finally:
                        MapsScraper._active_drivers.discard(driver)

        phones_found = sum(1 for l in leads if l['phone'] != 'Ver na Web')
        print(f"[Maps] 📊 Final: {len(leads)} leads | {phones_found} com telefone real")
        return leads


if __name__ == "__main__":
    scraper = MapsScraper(headless=False)  # headless=False pra ver o que acontece
    resultados = scraper.fetch_leads("Barbearia", "Sao Jose dos Campos", max_leads=5)
    print(f"\n✅ Total: {len(resultados)}")
    for r in resultados:
        print(r)
