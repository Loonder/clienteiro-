from fpdf import FPDF
import os
import unicodedata
import qrcode
import tempfile

# ---------------------------------------------------------------------------
# Utilitário de limpeza de string para fontes Latin-1 (core fpdf2)
# ---------------------------------------------------------------------------

def _clean(text) -> str:
    """
    Normaliza string para Latin-1 de forma segura.
    Usa NFKD para decompor acentos e recompõe via NFC antes de encodar,
    garantindo que ç, ã, é, etc. sejam preservados corretamente.
    """
    if not text:
        return ""
    t = unicodedata.normalize('NFC', str(text))
    try:
        # Testa se já é válido em latin-1
        t.encode('latin-1')
        return t
    except UnicodeEncodeError:
        # Decompõe e tenta novamente com substituição
        t = unicodedata.normalize('NFKD', t)
        return t.encode('latin-1', 'replace').decode('latin-1')


# ---------------------------------------------------------------------------
# PDFReporter
# ---------------------------------------------------------------------------

class PDFReporter:
    # Diretório raiz do projeto (core/ → ../)
    _PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    def __init__(self, data: dict, slug: str):
        self.data = data
        self.slug = slug

    # ------------------------------------------------------------------
    # Resolve logo de forma portável (sem paths hardcoded)
    # ------------------------------------------------------------------

    def _resolve_logo(self) -> str | None:
        """
        Tenta, em ordem:
        1. Logo enviada pelo usuário (já salva em disco)
        2. Logo padrão em static/img/logo.png (relativo ao projeto)
        3. Sem logo (None)
        """
        # 1. Logo do usuário
        user_logo = self.data.get('logo_url')
        if user_logo and os.path.isfile(str(user_logo)):
            return str(user_logo)

        # 2. Logo padrão do projeto
        for candidate in ('static/img/logo.png', 'static/img/logo.jpg', 'static/logo.png'):
            path = os.path.join(self._PROJECT_ROOT, candidate)
            if os.path.isfile(path):
                return path

        return None  # 3. Nenhuma logo disponível

    # ------------------------------------------------------------------
    # Geração do PDF
    # ------------------------------------------------------------------

    def generate(self, output_path: str) -> None:
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.set_auto_page_break(auto=False)
        pdf.add_page()

        # ── IA Predictive Insights ─────────────────────────────────────
        pdf.set_font("helvetica", 'B', 12)
        pdf.set_text_color(255, 106, 0)
        pdf.cell(0, 10, _clean("🎯 INSIGHTS PREDITIVOS (IA)"), 0, 1)
        pdf.set_font("helvetica", '', 10)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 7, _clean(f"Probabilidade de Fechamento: {self.data.get('conversion_prediction', 'N/A')}"), 0, 1)
        pdf.set_font("helvetica", 'B', 10)
        pdf.cell(0, 7, _clean(f"Próxima Ação Recomendada: {self.data.get('next_action', 'N/A')}"), 0, 1)
        pdf.ln(5)

        # ── Abordagem sugerida ────────────────────────────────────────
        # ── Fundo e moldura ──────────────────────────────────────────
        pdf.set_fill_color(250, 250, 250)
        pdf.rect(0, 0, 210, 297, 'F')

        # Barra lateral Clienteiro Orange
        pdf.set_fill_color(255, 106, 0)
        pdf.rect(0, 0, 5, 297, 'F')

        # ── Header Branco ─────────────────────────────────────────
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(5, 0, 205, 50, 'F')

        logo_path = self._resolve_logo()
        if logo_path:
            try:
                pdf.image(logo_path, x=12, y=10, h=28)
            except Exception as img_err:
                print(f"[Reporter] Logo ignorada: {img_err}")

        pdf.set_y(13)
        pdf.set_font("helvetica", 'B', 26)
        pdf.set_text_color(255, 106, 0)
        pdf.cell(195, 12, "CLIENTEIRO", 0, 1, 'R')

        pdf.set_font("helvetica", 'I', 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(195, 6, _clean("AUTOMAÇÃO INTELIGENTE DE CLIENTES"), 0, 1, 'R')

        pdf.set_font("helvetica", 'B', 8)
        pdf.set_text_color(180, 180, 180)
        pdf.set_xy(150, 35)
        pdf.cell(50, 5, _clean("[ CERTIFICADO CLIENTEIRO 2026 ]"), 0, 1, 'R')

        # ── Dados do usuário ──────────────────────────────────────────
        pdf.set_text_color(40, 40, 40)
        pdf.set_left_margin(15)
        pdf.set_y(55)

        user_name = self.data.get('user_name', 'Líder')
        company = self.data.get('company_name', 'Sua Empresa')

        pdf.set_font("helvetica", 'B', 18)
        pdf.cell(0, 10, _clean(f"Relatório VIP: {user_name}"), 0, 1)

        phone = str(self.data.get('user_phone', '') or '')
        if phone:
            suffix = _clean(" [BASE DE PROSPECÇÃO AUTORIZADA]") \
                     if str(self.data.get('can_call', '')).lower() in ('true', '1', 'on') else ''
            pdf.set_font("helvetica", 'B', 9)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(0, 5, f"WhatsApp: {phone}{suffix}", 0, 1)

        pdf.set_font("helvetica", '', 11)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 7, _clean(f"Análise de Mercado para {company}"), 0, 1)
        pdf.ln(2)

        # ── Grid de diagnóstico ───────────────────────────────────────
        pdf.set_fill_color(240, 240, 240)
        pdf.set_draw_color(212, 175, 55)
        pdf.set_line_width(0.3)
        grid_y = pdf.get_y()
        pdf.rect(15, grid_y, 180, 25, 'FD')

        pdf.set_xy(20, grid_y + 5)
        pdf.set_font("helvetica", 'B', 9)
        self._kv_row(pdf, "SEGMENTO ATUAL:", self.data.get('nicho', 'N/A').upper())
        pdf.set_x(20)
        self._kv_row(pdf, "LOCALIZAÇÃO:",    self.data.get('city', 'N/A').upper())
        pdf.set_x(20)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(40, 5, _clean("STATUS CLIENTEIRO:"), 0, 0)
        pdf.set_text_color(255, 106, 0)
        pdf.set_font("helvetica", 'B', 10)
        pdf.cell(100, 5, _clean(self.data.get('diagnosis_level', 'N/A').upper()), 0, 1)

        pdf.set_y(grid_y + 30)

        # ── Score ─────────────────────────────────────────────────────
        score = int(self.data.get('clienteiro_score', 15))
        score = max(0, min(100, score))
        pdf.set_font("helvetica", 'B', 14)
        pdf.set_text_color(15, 15, 15)
        pdf.cell(0, 10, _clean("RESULTADO DO CLIENTEIRO SCORE"), 0, 1)

        bar_y = pdf.get_y()
        pdf.set_fill_color(220, 220, 220)
        pdf.rect(15, bar_y, 180, 6, 'F')
        pdf.set_fill_color(255, 106, 0)
        pdf.rect(15, bar_y, 1.8 * score, 6, 'F')

        pdf.set_y(bar_y + 8)
        pdf.set_font("helvetica", 'B', 11)
        pdf.set_text_color(255, 106, 0)
        pdf.cell(180, 8, _clean(f"POTENCIAL DE DOMÍNIO: {score}%"), 0, 1, 'R')
        pdf.ln(2)

        # ── Comparativo de Mercado (UAU) ─────────────────────────────
        pdf.set_fill_color(245, 245, 245)
        pdf.rect(15, pdf.get_y(), 180, 20, 'F')
        pdf.set_xy(20, pdf.get_y() + 4)
        pdf.set_font("helvetica", 'B', 10)
        pdf.set_text_color(11, 17, 32)
        pdf.cell(0, 5, _clean("BENCHMARK INDIVIDUAL VS MÉDIA DO MERCADO (LOCAL)"), 0, 1)
        
        pdf.set_font("helvetica", '', 8)
        pdf.set_text_color(80, 80, 80)
        market_avg = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                city_val = self.data.get('city')
                nicho_val = self.data.get('nicho')

                if city_val and nicho_val:
                    cur.execute(
                        'SELECT AVG(clienteiro_score) as avg FROM internal_leads WHERE city = %s AND nicho = %s',
                        (city_val, nicho_val)
                    )
                    row = cur.fetchone()
                    market_avg = row['avg'] if row and row.get('avg') is not None else None

                if market_avg is None and nicho_val:
                    cur.execute(
                        'SELECT AVG(clienteiro_score) as avg FROM internal_leads WHERE nicho = %s',
                        (nicho_val,)
                    )
                    row = cur.fetchone()
                    market_avg = row['avg'] if row and row.get('avg') is not None else None

                if market_avg is None:
                    cur.execute('SELECT AVG(clienteiro_score) as avg FROM internal_leads')
                    row = cur.fetchone()
                    market_avg = row['avg'] if row and row.get('avg') is not None else None

                if market_avg is None:
                    cur.execute("SELECT value FROM system_config WHERE key = 'market_avg_score'")
                    row = cur.fetchone()
                    if row and row.get('value'):
                        try:
                            market_avg = float(row['value'])
                        except Exception:
                            market_avg = None
            conn.close()
        except Exception:
            market_avg = None

        if market_avg is None:
            diff_text = None
        else:
            diff = score - float(market_avg)
            diff_text = f"+{diff}% acima da média" if diff >= 0 else f"{diff}% abaixo da média"

        if diff_text:
            pdf.cell(0, 5, _clean(f"Sua empresa está {diff_text} em comparação com outros {self.data.get('nicho', 'negócios')} em {self.data.get('city', 'sua região')}."), 0, 1)
        else:
            pdf.cell(0, 5, _clean("Base histórica insuficiente para comparação local no momento."), 0, 1)
        pdf.ln(6)

        # ── Radar de oportunidades ────────────────────────────────────
        pdf.set_font("helvetica", 'B', 12)
        pdf.set_text_color(11, 17, 32)
        pdf.cell(0, 8, _clean("RADAR DE OPORTUNIDADES"), 0, 1)
        pdf.ln(1)

        radar_labels = [
            "Volume de Leads",
            "Qualidade do Funil",
            "Alcance Digital",
            "Taxa de Conversão",
        ]
        for i, label in enumerate(radar_labels):
            pdf.set_font("helvetica", 'B', 9)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(50, 6, _clean(label), 0, 0)
            bar_w = 125
            filled = (score / 100) * bar_w if i % 2 == 0 else (score / 120) * bar_w
            filled = min(filled, bar_w)
            pdf.set_fill_color(230, 230, 230)
            pdf.rect(65, pdf.get_y() + 1, bar_w, 4, 'F')
            pdf.set_fill_color(11, 17, 32)
            pdf.rect(65, pdf.get_y() + 1, filled, 4, 'F')
            pdf.ln(6)

        pdf.ln(4)

        # Tabela de leads ───────────────────────────────────────────
        leads = self.data.get('strategic_leads', [])[:5]
        leads = [lead for lead in leads if lead.get('source')]
        
        # Puxa telefone do Bot da configuração (Fallback para o admin se não achar)
        from core.db_manager import get_db_connection
        agency_phone = "11916722043" # Fallback
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM system_config WHERE key IN ('bot_phone', 'admin_phones') ORDER BY key DESC LIMIT 1")
                row = cur.fetchone()
                if row: agency_phone = str(row['value']).replace('55', '', 1)
            conn.close()
        except: pass

        agency_wpp = f"https://wa.me/55{agency_phone}?text=Ola!+Recebi+o+Clienteiro+e+quero+escalar+minhas+vendas."

        if not leads:
            pdf.set_font("helvetica", 'B', 12)
            pdf.set_text_color(200, 50, 50)
            pdf.cell(180, 8, _clean("ALERTA: OCEANO AZUL REVELADO"), 0, 1, 'L')
            
            pdf.set_font("helvetica", '', 10)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(120, 5, _clean("Não conseguimos expor leads imediatamente com os dados fornecidos. A concorrência digital está oculta ou mal posicionada. Nossa agência possui mineração avançada em bancos de dados ocultos."), 0, 'L')
            
            # Desenha QR CTA
            import tempfile
            qr_path = os.path.join(tempfile.gettempdir(), f"qr_cta_{self.slug}.png")
            self._generate_qr(agency_wpp, qr_path)
            pdf.image(qr_path, x=145, y=pdf.get_y() - 20, w=35)
            
            pdf.set_font("helvetica", 'B', 9)
            pdf.set_text_color(11, 17, 32)
            pdf.set_xy(140, pdf.get_y() + 16)
            pdf.cell(45, 5, _clean("ESCANEIE PARA AJUDA ->"), 0, 1, 'C')

            pdf.ln(8)
            
        if leads:
            type_focus = self.data.get('type_focus', 'b2b')
            title = "PERSONAS DE IMPACTO & INFLUENCIADORES" \
                    if type_focus == 'b2p' else "OPORTUNIDADES DE ALTO IMPACTO"

            pdf.set_fill_color(11, 17, 32)
            pdf.set_font("helvetica", 'B', 11)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(180, 10, _clean(f"  {title}"), 0, 1, 'L', True)

            # Cabeçalho da tabela
            pdf.set_fill_color(255, 106, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("helvetica", 'B', 8)
            pdf.cell(80, 8, _clean("IDENTIFICAÇÃO DA OPORTUNIDADE"),    1, 0, 'C', True)
            pdf.cell(35, 8, _clean("STATUS WEB"),               1, 0, 'C', True)
            pdf.cell(15, 8, _clean("SCORE"),                    1, 0, 'C', True)
            pdf.cell(50, 8, _clean("FONTE ESTRATÉGICA"),        1, 1, 'C', True)

            # Linhas
            pdf.set_font("helvetica", '', 7)
            import tempfile
            
            for idx, lead in enumerate(leads):
                pdf.set_text_color(40, 40, 40)
                pdf.cell(80, 7, _clean(str(lead.get('name', ''))[:42]), 1, 0)
                pdf.cell(35, 7, _clean(str(lead.get('phone', 'Ver na Web'))), 1, 0, 'C')

                rating = lead.get('rating', 4.5)
                pdf.cell(15, 7, f"{rating:.1f} *", 1, 0, 'C')

                source = str(lead.get('source', ''))
                display = self._format_source_url(source)
                
                pdf.set_text_color(30, 80, 150)
                
                # Se for o primeiro lead e tiver URL, desenhamos um mini QR Code
                if idx == 0 and source.startswith('http'):
                    pdf.cell(50, 7, _clean(" + [Acesso via QR Code]"), 1, 1, 'C', link=source)
                    # Coloca o QR sobre a linha (bem pequetito)
                    qr_lead = os.path.join(tempfile.gettempdir(), f"qr_lead_{self.slug}.png")
                    self._generate_qr(source, qr_lead)
                    # pdf.get_y() já desceu 7 pra prox linha por causa do ln=1, então subimos
                    pdf.image(qr_lead, x=186, y=pdf.get_y() - 6.5, w=6)
                else:
                    pdf.cell(50, 7, _clean(display), 1, 1, 'C', link=source)
                    
                pdf.set_text_color(40, 40, 40)

        pdf.ln(4)

        # ── Plano de Ação ─────────────────────────────────────────────
        pdf.set_font("helvetica", 'B', 12)
        pdf.set_text_color(11, 17, 32)
        pdf.cell(0, 8, _clean("PLANO DE AÇÃO ESTRATÉGICO"), 0, 1)

        pdf.set_font("helvetica", '', 9)
        pdf.set_text_color(60, 60, 60)
        # Limita largura para evitar quebras estranhas e garante espaço vertical
        for rec in self.data.get('recommendations', [])[:3]:
            # Se já estiver muito perto do fim, para de imprimir recomendações
            if pdf.get_y() > 235:
                break
            pdf.multi_cell(170, 5, _clean(f"[+] {rec}"), 0, 'L')

        # ── CTA (QR Code Principal) ──────────────────────────────────
        if leads:
            # Garante que o CTA fique sempre no rodapé, mas sem sobrepor texto
            cta_y = 245
            pdf.set_y(cta_y)
            pdf.set_fill_color(240, 240, 240)
            pdf.set_draw_color(212, 175, 55)
            pdf.rect(15, cta_y, 180, 22, 'FD')
            
            pdf.set_xy(20, cta_y + 3)
            pdf.set_font("helvetica", 'B', 11)
            pdf.set_text_color(11, 17, 32)
            pdf.cell(130, 6, _clean("QUER TER ACESSO À LISTA COMPLETA?"), 0, 1)
            pdf.set_x(20)
            pdf.set_font("helvetica", '', 10)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(130, 5, _clean("Escaneie para falar direto com o estrategista e liberar mais dados."), 0, 'L')

            qr_path_cta = os.path.join(tempfile.gettempdir(), f"qr_cta_leads_{self.slug}.png")
            self._generate_qr(agency_wpp, qr_path_cta)
            # QR centralizado no box (h=22, logo w=20 em y=cta_y+1)
            pdf.image(qr_path_cta, x=168, y=cta_y + 1, w=20)

        # ── Footer ────────────────────────────────────────────────────
        pdf.set_y(272)
        pdf.set_fill_color(11, 17, 32)
        pdf.rect(5, 272, 205, 25, 'F')

        pdf.set_y(277)
        pdf.set_font("helvetica", 'B', 10)
        pdf.set_text_color(255, 106, 0)
        pdf.cell(200, 5, _clean("CERTIFICADO DE AUTORIDADE CLIENTEIRO 2026"), 0, 1, 'C')

        pdf.set_font("helvetica", 'I', 8)
        pdf.set_text_color(200, 200, 200)
        pdf.cell(200, 5, _clean("Este diagnóstico é um ativo confidencial do Clienteiro Pro."), 0, 1, 'C')

        pdf.output(output_path)
        print(f"[Reporter] PDF gerado com sucesso: {output_path}")

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _kv_row(pdf: FPDF, label: str, value: str) -> None:
        pdf.set_font("helvetica", 'B', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(40, 5, _clean(label), 0, 0)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(100, 5, _clean(value), 0, 1)

    @staticmethod
    def _generate_qr(url: str, filepath: str):
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0B1120", back_color="white")
        img.save(filepath)

    @staticmethod
    def _format_source_url(url: str) -> str:
        """Converte URL completa em exibição curta mas legível."""
        if not url:
            return "Sem URL"
        url = url.split('?')[0]          # Remove query string
        url = url.replace('https://', '').replace('http://', '').replace('www.', '')
        return url[:38] + "…" if len(url) > 38 else url
