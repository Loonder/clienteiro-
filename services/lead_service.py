import os
import json
import threading
import requests
from datetime import datetime
from werkzeug.utils import secure_filename
from core.processor import BusinessProcessor
from core.reporter import PDFReporter
from core.db_manager import get_db_connection
from services.lgpd_service import LGPDService

from concurrent.futures import ThreadPoolExecutor

class LeadService:
    # Pool limitado para evitar explosão de threads na VPS
    _executor = ThreadPoolExecutor(max_workers=4)
    @staticmethod
    def process_submission(form_data, logo_file, session_data, app_config):
        """
        Handles the entire lead processing workflow: validation, enrichment, 
        persistence, PDF generation, and notifications.
        """
        # 1. Basic Extraction & Sanitization
        company_name = LeadService._clean_text(form_data.get('company_name'), 'Sem Nome', 80)
        user_name = session_data.get('gestor_nome') or LeadService._clean_text(form_data.get('user_name'), 'Líder', 60)
        nicho = LeadService._clean_text(form_data.get('nicho'), 'Empresas', 60)
        city = LeadService._clean_text(form_data.get('city'), 'Brasil', 60)
        user_phone = LeadService._clean_text(form_data.get('user_phone'), '', 20)
        can_call = str(form_data.get('can_call', '')).strip().lower() in {'1', 'true', 'yes', 'on', 'sim'}
        if not can_call:
            return {'ok': False, 'error': 'Consentimento LGPD obrigatorio para continuar.'}

        # 1.5. Busca de Cache (Evita reprocessamento desnecessário)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT slug, pdf_path FROM internal_leads 
                    WHERE LOWER(company_name) = LOWER(%s) AND LOWER(city) = LOWER(%s)
                    ORDER BY id DESC LIMIT 1
                ''', (company_name, city))
                cached = cur.fetchone()
                if cached and cached.get('pdf_path'):
                    return {'ok': True, 'slug': cached['slug'], 'pdf_url': f"/download/{cached['pdf_path']}"}
        except Exception as e:
            print(f"[CACHE] Erro na busca de histórico: {e}")
        finally:
            conn.close()
        
        # 2. Limit Check
        nivel = session_data.get('nivel_acesso')
        gid = session_data.get('gestor_id')
        if nivel == 'cliente' and gid:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute('SELECT gen_count, plano FROM gestores WHERE id = %s', (gid,))
                user = cur.fetchone()
                plano = str(user.get('plano') or 'gratis').lower() if user else 'gratis'
                gen_count = int(user.get('gen_count') or 0) if user else 0
                if plano != 'pro' and gen_count >= 3:
                    conn.close()
                    return {'ok': False, 'limit_reached': True, 'error': 'Limite atingido!'}
                cur.execute('UPDATE gestores SET gen_count = gen_count + 1 WHERE id = %s', (gid,))
                conn.commit()
            conn.close()

        # 3. Preparation
        safe_name = secure_filename(company_name).replace('-', '_') or 'SemNome'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        slug = f"{safe_name}_{timestamp}"
        comp_dir = os.path.join(app_config['DATA_DIR'], slug)
        os.makedirs(comp_dir, exist_ok=True)

        # 4. Enrichment
        safe_data = {
            **form_data,
            'company_name': company_name,
            'user_name': user_name,
            'nicho': nicho,
            'city': city,
            'user_phone': user_phone,
            'gestor_id': gid,
            'can_call': can_call,
        }
        processor = BusinessProcessor(safe_data)
        enriched = processor.process()

        # 5. Logo Handling
        if logo_file and logo_file.filename:
            ext = os.path.splitext(secure_filename(logo_file.filename))[1].lower()
            if ext in {'.png', '.jpg', '.jpeg', '.webp'}:
                logo_path = os.path.join(comp_dir, f"logo{ext}")
                logo_file.save(logo_path)
                enriched['logo_url'] = logo_path

        # 6. Database Persistence
        pdf_filename = f"Diagnostico_{safe_name}_{timestamp}.pdf"
        consent_ip = LeadService._clean_text(form_data.get('_client_ip'), 'unknown', 80)
        consent_version = LeadService._clean_text(form_data.get('_consent_version'), '2026-03-28', 40)
        legal_basis = LeadService._clean_text(os.getenv('LEGAL_BASIS_DEFAULT', 'consent'), 'consent', 40)
        retention_until = LGPDService.compute_retention_until()
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO internal_leads
                        (user_name, company_name, nicho, city, phone, type_focus, consent,
                         consent_at, consent_ip, consent_version, legal_basis,
                         clienteiro_score, pdf_path, retention_until, gestor_id, slug)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    user_name,
                    company_name,
                    nicho,
                    city,
                    user_phone,
                    safe_data.get('type_focus', 'b2b'),
                    1,
                    consent_ip,
                    consent_version,
                    legal_basis,
                    enriched.get('clienteiro_score', 0),
                    pdf_filename,
                    retention_until,
                    gid,
                    slug
                ))
                conn.commit()
            conn.close()
        except Exception as e:
            print(f"[LeadService] DB Error: {e}")

        # 7. PDF Generation
        reports_dir = app_config.get('REPORTS_DIR') or os.path.join(app_config['DATA_DIR'], 'reports')
        fallback_reports_dir = app_config.get('REPORTS_FALLBACK_DIR') or os.path.join(app_config['DATA_DIR'], 'reports_fallback')
        pdf_path = os.path.join(reports_dir, pdf_filename)
        try:
            os.makedirs(reports_dir, exist_ok=True)
            reporter = PDFReporter(enriched, slug)
            reporter.generate(pdf_path)
        except Exception as e:
            print(f"[LeadService] PDF Error (dir principal): {e}")
            try:
                # Fallback seguro quando /app/reports estiver sem permissão de escrita.
                os.makedirs(fallback_reports_dir, exist_ok=True)
                fallback_pdf_path = os.path.join(fallback_reports_dir, pdf_filename)
                reporter = PDFReporter(enriched, slug)
                reporter.generate(fallback_pdf_path)
                pdf_path = fallback_pdf_path
                print(f"[LeadService] PDF gerado no fallback: {fallback_pdf_path}")
            except Exception as e2:
                print(f"[LeadService] PDF Error (fallback): {e2}")
                return {'ok': False, 'error': 'Erro ao gerar PDF'}

        # 8. Async Notification (WhatsApp) - Pool Gerenciado
        if user_phone:
            LeadService._executor.submit(LeadService._send_whatsapp, user_phone, user_name, company_name, pdf_path)

        return {'ok': True, 'slug': slug, 'pdf_url': f'/download/{pdf_filename}'}

    @staticmethod
    def _try_dispatch_to_saasbot(phone, name, company, pdf_filename):
        base_url = os.getenv('SAASBOT_INTERNAL_URL', '').strip().rstrip('/')
        if not base_url:
            return False

        tenant_id = os.getenv('SAASBOT_TENANT_ID', 'default').strip() or 'default'
        api_secret = os.getenv('SAASBOT_API_SECRET', '').strip()
        url = f"{base_url}/internal/checkleads/offer/{tenant_id}"
        payload = {
            'phone': phone,
            'user_name': name,
            'company_name': company,
            'pdf_filename': pdf_filename,
            'dedupe_key': f'kiosk:{pdf_filename}:{phone}'
        }

        headers = {'Content-Type': 'application/json'}
        if api_secret:
            headers['x-bot-secret'] = api_secret

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if 200 <= resp.status_code < 300:
                print(f"[LeadService] Disparo direto no SaasBot OK: {phone}")
                return True

            print(f"[LeadService] SaasBot retornou {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[LeadService] Falha ao chamar SaasBot: {e}")

        return False

    @staticmethod
    def _send_whatsapp(phone, name, company, pdf_path):
        if os.getenv('BOT_PAUSED', 'false').lower() == 'true':
            print(f"[LeadService] PAUSADO: Pulando disparo de WhatsApp para {phone}.")
            return

        try:
            from core.db_manager import get_db_connection

            pdf_filename = os.path.basename(pdf_path)
            if LeadService._try_dispatch_to_saasbot(phone, name, company, pdf_filename):
                return
            
            conn = get_db_connection()
            with conn.cursor() as cur:
                # Garante que a Caixa Longe (Queue) existe
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS kiosk_webhooks (
                        id SERIAL PRIMARY KEY,
                        phone VARCHAR(30) NOT NULL,
                        user_name VARCHAR(150),
                        company_name VARCHAR(150),
                        pdf_filename VARCHAR(255),
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cur.execute('''
                    INSERT INTO kiosk_webhooks (phone, user_name, company_name, pdf_filename)
                    VALUES (%s, %s, %s, %s)
                ''', (phone, name, company, pdf_filename))
                
            conn.commit()
            conn.close()
            print(f"[LeadService] Enfileirado na Caixa Longe (Supabase) para o Bot Local: {phone}")
        except Exception as e:
            print(f"[LeadService] Fila Supabase Error: {e}")

    @staticmethod
    def _clean_text(value, fallback='', max_len=80):
        text = str(value or '').strip()
        text = ' '.join(text.split())
        return text[:max_len] if text else fallback
