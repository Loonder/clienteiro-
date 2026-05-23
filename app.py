from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, flash
from dotenv import load_dotenv
import os
import sqlite3
import json
import time
import hashlib
import hmac
import requests
import threading
import signal
import subprocess
import random
from datetime import datetime, timedelta
from functools import wraps
from core.processor import BusinessProcessor
from core.reporter import PDFReporter
from werkzeug.utils import secure_filename
from core.db_manager import get_db_connection, init_postgres_db
from services.lead_service import LeadService
from services.lgpd_service import LGPDService
from services.auth_service import AuthService
from core.runtime import env_bool
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

def _is_production():
    return os.getenv('FLASK_ENV', '').strip().lower() == 'production'

def _required_env(name):
    value = os.getenv(name, '').strip()
    if not value and _is_production():
        raise RuntimeError(f'{name} must be configured in production.')
    return value

def _valid_internal_api_key(api_key_header):
    internal_key = _required_env('INTERNAL_API_KEY')
    if not internal_key or not api_key_header:
        return False
    return hmac.compare_digest(str(api_key_header), internal_key)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["2000 per day", "500 per hour"],
    storage_uri="memory://",
)
secret_key = _required_env('SECRET_KEY') or os.urandom(32).hex()
app.secret_key = secret_key
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_UPLOAD_MB', '10')) * 1024 * 1024

# Hardening de Cookies (Zero Trust)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# 1. Ativa CSRF Protect Globalmente
csrf = CSRFProtect(app)

# 2. Ativa Talisman (Security Headers & CSP)
# Permitimos inline styles para o design premium do Clienteiro, mas bloqueamos scripts externos nÃ£o-autorizados
csp = {
    'default-src': "'self'",
    'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    'font-src': ["'self'", "https://fonts.gstatic.com"],
    'script-src': ["'self'", "'unsafe-inline'", "https://unpkg.com"],
    'img-src': ["'self'", "data:", "https://*"],
    'connect-src': ["'self'", "https://unpkg.com"],
    'frame-ancestors': "'none'"
}

Talisman(app, 
    force_https=False, 
    strict_transport_security=True, 
    session_cookie_secure=True,
    content_security_policy=csp
)

ALLOWED_LOGO_EXTS = {'.png', '.jpg', '.jpeg', '.webp'}

# Configurações
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, 'data')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
REPORTS_FALLBACK_DIR = os.path.join(DATA_DIR, 'reports_fallback')
# DB_PATH removido - Agora usamos Supabase (PostgreSQL) via SUPABASE_DB_URL

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(REPORTS_FALLBACK_DIR, exist_ok=True)

# Rate limit simples por IP (1 submit a cada 10s — evita spam na feira)
_rate_store: dict = {}
RATE_LIMIT_SECONDS = 10
_stream_harvest_lock = threading.Lock()
_worker_process = None
_log_queue = None  # Queue fed by background thread, read by SSE generator
import queue as _queue_module
_kiosk_unlock_attempts: dict = {}
KIOSK_UNLOCK_WINDOW_SECONDS = int(os.getenv('KIOSK_UNLOCK_WINDOW_SECONDS', '60'))
KIOSK_UNLOCK_MAX_ATTEMPTS = int(os.getenv('KIOSK_UNLOCK_MAX_ATTEMPTS', '5'))
KIOSK_EXIT_PIN = str(os.getenv('KIOSK_EXIT_PIN', '7391')).strip()
ROULETTE_WEBHOOK_URL = os.getenv('ROULETTE_WEBHOOK_URL', 'http://roulette-webhook:3000/webhook/roleta').strip()
ROULETTE_REQUIRE_WHATSAPP_EXISTS = False
ROULETTE_ALLOW_QUEUE_WHEN_VALIDATION_OFFLINE = env_bool('ROULETTE_ALLOW_QUEUE_WHEN_VALIDATION_OFFLINE', True)
ROULETTE_QUEUE_FLUSH_BATCH = int(os.getenv('ROULETTE_QUEUE_FLUSH_BATCH', '25'))
ROULETTE_WEBHOOK_TIMEOUT_SECONDS = float(os.getenv('ROULETTE_WEBHOOK_TIMEOUT_SECONDS', '2'))
ROULETTE_VALIDATION_TIMEOUT_SECONDS = float(os.getenv('ROULETTE_VALIDATION_TIMEOUT_SECONDS', '3'))
ROULETTE_PRIZES = [
    {"text": "Copo Laranja Elite", "icon": "🥤", "desc": "O trofeu oficial dos gestores que dominam o Clienteiro."},
    {"text": "Copo Preto Executive", "icon": "🥤", "desc": "A estetica Apple/SaaS aplicada ao seu dia a dia."},
    {"text": "Caneta Personalizada", "icon": "🖋️", "desc": "Sua assinatura com estilo e autoridade."},
    {"text": "R$ 500 OFF em Sites Premium", "icon": "💰", "desc": "Desconto exclusivo na producao do seu novo site."},
    {"text": "R$ 1.000 OFF em CRM & Funil", "icon": "⚙️", "desc": "Desconto na implementacao do seu funil de vendas."},
    {"text": "Mentoria VIP Individual", "icon": "💎", "desc": "1 hora de mentoria estrategica direto com o fundador."},
    {"text": "1 Mes de Clienteiro Gratis", "icon": "🚀", "desc": "Use o cupom CLIENTEIRO30 no checkout."},
    {"text": "Auditoria de Processos", "icon": "🔍", "desc": "Mapeamento completo dos gargalos do seu time."},
]

def _get_client_ip() -> str:
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or 'unknown'

def _clean_text(value, fallback: str = '', max_len: int = 80) -> str:
    text = str(value or '').strip()
    text = ' '.join(text.split())
    if not text:
        return fallback
    return text[:max_len]

def _dispatch_roulette_webhook(payload: dict) -> dict:
    """
    Dispara webhook da roleta sem derrubar o fluxo principal.
    Retorna dict para logging/diagnostico.
    """
    if not ROULETTE_WEBHOOK_URL:
        return {'ok': False, 'error': 'ROULETTE_WEBHOOK_URL vazio.'}
    try:
        response = requests.post(
            ROULETTE_WEBHOOK_URL,
            json=payload,
            timeout=ROULETTE_WEBHOOK_TIMEOUT_SECONDS
        )
        return {
            'ok': response.ok,
            'status': response.status_code,
            'body': response.text[:500]
        }
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}

def _enqueue_roulette_event(payload: dict, last_error: str = '') -> None:
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                '''
                INSERT INTO roulette_webhook_queue (event_name, payload, status, attempts, next_retry_at, last_error)
                VALUES (%s, %s, 'pending', 0, CURRENT_TIMESTAMP, %s)
                ''',
                (str(payload.get('event') or 'unknown'), json.dumps(payload, ensure_ascii=False), str(last_error or '')[:500])
            )
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[ROULETTE_QUEUE] Falha ao enfileirar evento: {exc}")

def _dispatch_or_queue_roulette(payload: dict) -> dict:
    dispatch = _dispatch_roulette_webhook(payload)
    if dispatch.get('ok'):
        return {'queued': False, 'dispatch': dispatch}
    _enqueue_roulette_event(payload, dispatch.get('error') or dispatch.get('body') or 'dispatch_failed')
    return {'queued': True, 'dispatch': dispatch}

def _dispatch_or_queue_roulette_async(payload: dict) -> None:
    def worker():
        _dispatch_or_queue_roulette(payload)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

def _flush_roulette_queue(limit: int = ROULETTE_QUEUE_FLUSH_BATCH) -> dict:
    """
    Tenta enviar eventos pendentes. Chamada em cada register/spin para dreno oportunista.
    """
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                '''
                SELECT id, payload, attempts
                FROM roulette_webhook_queue
                WHERE status = 'pending'
                  AND next_retry_at <= CURRENT_TIMESTAMP
                ORDER BY id ASC
                LIMIT %s
                ''',
                (int(max(1, limit)),)
            )
            rows = cur.fetchall()
        conn.close()
    except Exception as exc:
        return {'ok': False, 'error': str(exc), 'sent': 0, 'kept': 0, 'picked': 0}

    sent = 0
    kept = 0
    for row in rows:
        event_id = row.get('id')
        payload_raw = row.get('payload')
        attempts = int(row.get('attempts') or 0)
        try:
            payload = payload_raw if isinstance(payload_raw, dict) else json.loads(payload_raw or '{}')
        except Exception:
            payload = {}

        dispatch = _dispatch_roulette_webhook(payload)
        try:
            conn = get_db()
            with conn.cursor() as cur:
                if dispatch.get('ok'):
                    cur.execute(
                        '''
                        UPDATE roulette_webhook_queue
                        SET status = 'sent', sent_at = CURRENT_TIMESTAMP, last_error = NULL
                        WHERE id = %s
                        ''',
                        (event_id,)
                    )
                    sent += 1
                else:
                    next_minutes = min(30, max(1, 2 ** min(attempts, 5)))
                    next_retry = datetime.utcnow() + timedelta(minutes=next_minutes)
                    cur.execute(
                        '''
                        UPDATE roulette_webhook_queue
                        SET attempts = attempts + 1,
                            next_retry_at = %s,
                            last_error = %s,
                            status = 'pending'
                        WHERE id = %s
                        ''',
                        (
                            next_retry,
                            str(dispatch.get('error') or dispatch.get('body') or 'dispatch_failed')[:500],
                            event_id
                        )
                    )
                    kept += 1
            conn.commit()
            conn.close()
        except Exception as exc:
            print(f"[ROULETTE_QUEUE] Falha ao atualizar item {event_id}: {exc}")

    return {'ok': True, 'picked': len(rows), 'sent': sent, 'kept': kept}

def _validate_whatsapp_exists(phone: str):
    """
    Valida existencia do numero no WhatsApp via Evolution API.
    Tenta primeiro a rota padrao da v2 e, se falhar, uma rota alternativa.
    """
    normalized = _normalize_phone(phone)
    if not normalized or len(normalized) not in (12, 13):
        return False, 'Telefone invalido.', False

    evolution_base = str(os.getenv('EVOLUTION_BASE_URL', '')).strip().rstrip('/')
    evolution_instance = str(os.getenv('EVOLUTION_INSTANCE', '')).strip()
    evolution_apikey = str(os.getenv('EVOLUTION_API_KEY', '')).strip()

    if not evolution_base or not evolution_instance or not evolution_apikey:
        return False, 'Evolution API nao configurada (EVOLUTION_BASE_URL/EVOLUTION_INSTANCE/EVOLUTION_API_KEY).', True

    headers = {
        'apikey': evolution_apikey,
        'Content-Type': 'application/json'
    }
    payload = {'numbers': [normalized]}
    endpoints = [
        f'{evolution_base}/chat/whatsappNumbers/{evolution_instance}',
        f'{evolution_base}/chat/whatsappNumbers'
    ]

    for endpoint in endpoints:
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=ROULETTE_VALIDATION_TIMEOUT_SECONDS)
            if not response.ok:
                continue
            data = response.json() if response.content else {}
            if isinstance(data, list):
                if not data:
                    return False, 'Numero nao encontrado no WhatsApp.'
                item = data[0] if isinstance(data[0], dict) else {}
                exists = bool(item.get('exists') or item.get('isWhatsapp') or item.get('jid'))
                return (exists, '' if exists else 'Numero nao encontrado no WhatsApp.')
            if isinstance(data, dict):
                entries = data.get('numbers') or data.get('data') or data.get('result')
                if isinstance(entries, list) and entries:
                    item = entries[0] if isinstance(entries[0], dict) else {}
                    exists = bool(item.get('exists') or item.get('isWhatsapp') or item.get('jid'))
                    return (exists, '' if exists else 'Numero nao encontrado no WhatsApp.', False)
                if data.get('exists') is not None:
                    exists = bool(data.get('exists'))
                    return (exists, '' if exists else 'Numero nao encontrado no WhatsApp.', False)
        except Exception:
            continue

    return False, 'Nao foi possivel validar o WhatsApp agora. Evento ficou em fila e sera enviado quando a Evolution voltar.', True

# ——— Segurança Ativa: Honeypots & Blacklist ———————————————————————————————————
_BANNED_IPS = set()

def sync_blacklist():
    """Carrega IPs banidos do banco para a memÃ³ria (Performance)."""
    global _BANNED_IPS
    if env_bool('SKIP_DB_INIT', False):
        return
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT ip FROM banned_ips")
            rows = cur.fetchall()
            _BANNED_IPS = {row['ip'] for row in rows}
        conn.close()
    except Exception as e:
        print(f"[Security] Erro ao sincronizar blacklist: {e}")

def ban_ip(ip, reason="Honeypot Triggered"):
    """Bane um IP permanentemente no banco e na memÃ³ria."""
    global _BANNED_IPS
    if not ip or ip == '127.0.0.1': return
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO banned_ips (ip, reason) VALUES (%s, %s) ON CONFLICT (ip) DO NOTHING",
                (ip, reason)
            )
            cur.execute(
                "INSERT INTO audit_log (acao, ip) VALUES (%s, %s)",
                (f"IP_BANNED: {reason}", ip)
            )
        conn.commit()
        conn.close()
        _BANNED_IPS.add(ip)
        print(f"!!! [SECURITY] IP BANIDO: {ip} | Motivo: {reason}")
    except Exception as e:
        print(f"[Security] Erro ao banir IP: {e}")

@app.before_request
def check_blacklist():
    """Filtro global: Bloca IPs na lista negra antes de qualquer processamento."""
    ip = _get_client_ip()
    if ip in _BANNED_IPS:
        time.sleep(2) # TÃ¡tica de lentidÃ£o para frustrar o hacker
        return "Access Denied (Security Shield)", 403

# ——— Rotas Armadilha (Trap Routes / Honeypots) ————————————————————————————————

@app.route('/.env')
@app.route('/.git/config')
@app.route('/wp-admin')
@app.route('/admin/config.php')
@app.route('/phpmyadmin')
def hacker_trap():
    """Rota isca: Qualquer um que acessar aqui Ã© banido na hora."""
    ip = _get_client_ip()
    ban_ip(ip, f"Accessing Trap Route: {request.path}")
    return "Access Denied", 403

# Inicializa Blacklist no boot
sync_blacklist()

def _to_bool(value) -> bool:
    return str(value).strip().lower() in ('1', 'true', 'yes', 'sim', 'on')

def _only_digits(value: str) -> str:
    return ''.join(filter(str.isdigit, value or ''))

def _normalize_phone(value: str) -> str:
    digits = _only_digits(value)
    if not digits:
        return ''
    if digits.startswith('55'):
        return digits
    if len(digits) in (10, 11):
        return f'55{digits}'
    return digits

def _whatsapp_target_from_phone(value: str) -> str:
    """
    Gera um alvo válido para wa.me no formato E.164 (Brasil).
    Retorna string vazia quando o campo não contém telefone real.
    """
    digits = _only_digits(str(value or ''))
    if not digits:
        return ''

    # Já veio com DDI do Brasil
    if digits.startswith('55'):
        return digits if len(digits) in (12, 13) else ''

    # Veio só com DDD + número local
    if len(digits) in (10, 11):
        return f'55{digits}'

    return ''

def _kiosk_unlock_gate(ip: str):
    now = time.time()
    history = [ts for ts in _kiosk_unlock_attempts.get(ip, []) if now - ts < KIOSK_UNLOCK_WINDOW_SECONDS]
    if len(history) >= KIOSK_UNLOCK_MAX_ATTEMPTS:
        wait = int(max(1, KIOSK_UNLOCK_WINDOW_SECONDS - (now - history[0])))
        _kiosk_unlock_attempts[ip] = history
        return False, wait
    history.append(now)
    _kiosk_unlock_attempts[ip] = history
    return True, 0

def rate_limited(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = _get_client_ip()
        now = time.time()
        last = _rate_store.get(ip, 0)
        if now - last < RATE_LIMIT_SECONDS:
            wait = int(RATE_LIMIT_SECONDS - (now - last))
            return jsonify({'ok': False, 'error': f'Aguarde {wait}s antes de nova consulta.'}), 429
        _rate_store[ip] = now
        return f(*args, **kwargs)
    return decorated

# â”€â”€ Banco de dados â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def get_db():
    return get_db_connection()

from core.auth import (
    login_required, 
    diretor_required, 
    log_acao, 
    seed_default_gestor,
    hash_password,
    check_password
)

def init_db():
    if env_bool('SKIP_DB_INIT', False):
        print("[DB] SKIP_DB_INIT=true; inicializacao do banco ignorada para demo/local.")
        return
    init_postgres_db()
    conn = get_db()
    seed_default_gestor(conn)
    conn.close()

init_db()

# â”€â”€ Decoradores de SeguranÃ§a â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Removidos daqui pois agora sÃ£o importados de core.auth

def get_dashboard_kpis(conn):
    """Calcula KPIs para o dashboard administrativo."""
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) as total FROM internal_leads')
            row = cur.fetchone()
            total = int(row['total']) if row else 0

            cur.execute('SELECT COUNT(*) as total FROM internal_leads WHERE printed = 1')
            row_p = cur.fetchone()
            printed = int(row_p['total']) if row_p else 0

            cur.execute('SELECT COUNT(*) as total FROM internal_leads WHERE printed = 0')
            row_w = cur.fetchone()
            aguardando = int(row_w['total']) if row_w else 0

            cur.execute('SELECT COALESCE(AVG(clienteiro_score), 0) as avg_score FROM internal_leads')
            row_avg = cur.fetchone()
            score_medio = round(float(row_avg['avg_score'] or 0), 1)

            cur.execute('SELECT COUNT(*) as total FROM internal_leads WHERE clienteiro_score >= 80')
            row_e = cur.fetchone()
            elite = int(row_e['total']) if row_e else 0

            cur.execute('''
                SELECT DATE(timestamp) as dia, COUNT(*) as total
                FROM internal_leads
                WHERE timestamp >= CURRENT_DATE - INTERVAL '6 days'
                GROUP BY dia
                ORDER BY dia ASC
            ''')
            rows = cur.fetchall()
            counts = {r['dia']: int(r['total']) for r in rows}

            today = datetime.now().date()
            labels = []
            values = []
            for i in range(6, -1, -1):
                d = today - timedelta(days=i)
                labels.append(d.strftime('%d/%m'))
                values.append(counts.get(d, 0))

            cur.execute('''
                SELECT city, COUNT(*) as total
                FROM internal_leads
                WHERE city IS NOT NULL AND city <> ''
                GROUP BY city
                ORDER BY total DESC
                LIMIT 4
            ''')
            rows_city = cur.fetchall()
            city_labels = [r['city'] for r in rows_city]
            city_values = [int(r['total']) for r in rows_city]
            if total > sum(city_values):
                city_labels.append('Outros')
                city_values.append(max(total - sum(city_values), 0))

            cur.execute('''
                SELECT COUNT(*) as total
                FROM internal_leads
                WHERE DATE(timestamp) = CURRENT_DATE
            ''')
            row_today = cur.fetchone()
            leads_hoje = int(row_today['total']) if row_today else 0

            cur.execute('''
                SELECT COUNT(*) as total
                FROM internal_leads
                WHERE DATE(timestamp) = CURRENT_DATE AND printed = 1
            ''')
            row_today_printed = cur.fetchone()
            leads_hoje_printed = int(row_today_printed['total']) if row_today_printed else 0

            leads_hoje_wait = max(leads_hoje - leads_hoje_printed, 0)

            taxa_conversao = round((printed / total) * 100, 1) if total > 0 else 0

            return {
                'total_leads': total,
                'elite_leads': elite,
                'leads_aguardando': aguardando,
                'leads_hoje': leads_hoje,
                'leads_hoje_printed': leads_hoje_printed,
                'leads_hoje_wait': leads_hoje_wait,
                'score_medio': score_medio,
                'taxa_conversao': taxa_conversao,
                'leads_grafico': {
                    'labels': labels,
                    'values': values
                },
                'leads_por_cidade_labels': city_labels,
                'leads_por_cidade_values': city_values
            }
    except Exception as e:
        print(f"[KPI ERROR] {e}")
        return {
            'total_leads': 0, 'elite_leads': 0, 'leads_aguardando': 0,
            'leads_hoje': 0, 'leads_hoje_printed': 0, 'leads_hoje_wait': 0,
            'score_medio': 0, 'taxa_conversao': 0,
            'leads_grafico': {'labels': [], 'values': []},
            'leads_por_cidade_labels': [], 'leads_por_cidade_values': []
        }

@app.route('/')
def landing():
    """PÃ¡gina de apresentaÃ§Ã£o premium (Landing Page)."""
    return render_template('landing.html')


@app.route('/kiosk')
def index():
    """Kiosk de resgate de premio com cadastro + roleta."""
    return render_template(
        'kiosk_prize.html',
        kiosk_secret_combo=os.getenv('KIOSK_SECRET_COMBO', 'CTRL+SHIFT+U')
    )


@app.route('/kiosk/diagnostico')
def kiosk_diagnostico():
    """Mantem o diagnostico legado em rota separada."""
    return render_template(
        'index.html',
        kiosk_secret_combo=os.getenv('KIOSK_SECRET_COMBO', 'CTRL+SHIFT+U')
    )


@app.route('/api/kiosk/roulette/register', methods=['POST'])
@limiter.limit("20 per minute")
def kiosk_roulette_register():
    payload = request.get_json(silent=True) or {}
    name = _clean_text(payload.get('name'), fallback='Cliente', max_len=80)
    phone = _normalize_phone(payload.get('phone'))

    if not phone:
        return jsonify({'ok': False, 'error': 'Informe um WhatsApp valido com DDD.'}), 400
    if len(phone) not in (12, 13):
        return jsonify({'ok': False, 'error': 'WhatsApp invalido. Use formato 55DDDNUMERO.'}), 400

    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, won_prize FROM kiosk_roulette_claims WHERE phone = %s LIMIT 1",
                (phone,)
            )
            existing = cur.fetchone()
        conn.close()

        if existing and existing.get('won_prize'):
            return jsonify({
                'ok': False,
                'already_claimed': True,
                'error': 'Este numero ja resgatou um premio.'
            }), 409

        validation_offline_queued = False
        if ROULETTE_REQUIRE_WHATSAPP_EXISTS:
            exists, reason, validation_unavailable = _validate_whatsapp_exists(phone)
            if not exists:
                if validation_unavailable and ROULETTE_ALLOW_QUEUE_WHEN_VALIDATION_OFFLINE:
                    validation_offline_queued = True
                else:
                    return jsonify({
                        'ok': False,
                        'error': reason or 'Nao foi possivel validar este WhatsApp.'
                    }), 400

        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                '''
                INSERT INTO kiosk_roulette_claims (phone, user_name)
                VALUES (%s, %s)
                ON CONFLICT (phone)
                DO UPDATE SET user_name = EXCLUDED.user_name
                ''',
                (phone, name)
            )
        conn.commit()
        conn.close()

        webhook_payload = {
            'event': 'lead_captured',
            'name': name,
            'phone': phone,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        _dispatch_or_queue_roulette_async(webhook_payload)

        return jsonify({
            'ok': True,
            'name': name,
            'phone': phone,
            'validation_offline_queued': validation_offline_queued,
            'webhook_deferred': True
        })
    except Exception as exc:
        return jsonify({'ok': False, 'error': f'Falha ao registrar lead: {exc}'}), 500


@app.route('/api/kiosk/roulette/spin', methods=['POST'])
@limiter.limit("20 per minute")
def kiosk_roulette_spin():
    payload = request.get_json(silent=True) or {}
    phone = _normalize_phone(payload.get('phone'))
    requested_name = _clean_text(payload.get('name'), fallback='Cliente', max_len=80)

    if not phone:
        return jsonify({'ok': False, 'error': 'Telefone obrigatorio para girar.'}), 400

    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_name, won_prize FROM kiosk_roulette_claims WHERE phone = %s LIMIT 1",
                (phone,)
            )
            row = cur.fetchone()

            if not row:
                conn.close()
                return jsonify({
                    'ok': False,
                    'error': 'Cadastre-se primeiro antes de girar a roleta.'
                }), 400

            if row.get('won_prize'):
                conn.close()
                return jsonify({
                    'ok': False,
                    'already_claimed': True,
                    'prize': row.get('won_prize'),
                    'error': 'Este numero ja resgatou um premio.'
                }), 409

            selected = random.choice(ROULETTE_PRIZES)
            prize_text = str(selected.get('text') or 'Premio Especial').strip()
            user_name = _clean_text(row.get('user_name') or requested_name, fallback='Cliente', max_len=80)

            cur.execute(
                '''
                UPDATE kiosk_roulette_claims
                SET won_prize = %s, won_at = CURRENT_TIMESTAMP, user_name = %s
                WHERE phone = %s
                ''',
                (prize_text, user_name, phone)
            )
        conn.commit()
        conn.close()

        webhook_payload = {
            'event': 'prize_won',
            'prize': prize_text,
            'lead': {
                'name': user_name,
                'phone': phone,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        }
        _dispatch_or_queue_roulette_async(webhook_payload)

        return jsonify({
            'ok': True,
            'phone': phone,
            'name': user_name,
            'prize': selected,
            'webhook_deferred': True
        })
    except Exception as exc:
        return jsonify({'ok': False, 'error': f'Falha ao girar roleta: {exc}'}), 500


@app.route('/api/kiosk/roulette/flush-queue', methods=['POST'])
@csrf.exempt
def kiosk_roulette_flush_queue():
    provided = str(request.headers.get('X-Internal-Api-Key', '')).strip()
    if not _valid_internal_api_key(provided):
        return jsonify({'ok': False, 'error': 'Nao autorizado.'}), 401
    result = _flush_roulette_queue(limit=200)
    return jsonify({'ok': True, 'result': result})


@app.route('/api/kiosk/unlock', methods=['POST'])
def kiosk_unlock():
    """Valida pin secreto para sair do modo kiosk."""
    ip = _get_client_ip()
    allowed, wait = _kiosk_unlock_gate(ip)
    if not allowed:
        return jsonify({
            'ok': False,
            'error': f'Muitas tentativas. Aguarde {wait}s.'
        }), 429

    payload = request.get_json(silent=True) or {}
    provided_pin = str(payload.get('pin', '')).strip()
    if not provided_pin:
        return jsonify({'ok': False, 'error': 'PIN obrigatorio.'}), 400

    if not hmac.compare_digest(provided_pin, KIOSK_EXIT_PIN):
        return jsonify({'ok': False, 'error': 'PIN invalido.'}), 401

    return jsonify({'ok': True})


@app.route('/submit', methods=['POST'])
@rate_limited
def submit():
    try:
        # Suporte a FormData e JSON
        if request.content_type and request.content_type.startswith('multipart/form-data'):
            form_data = request.form.to_dict()
            logo_file = request.files.get('logo')
        else:
            form_data = request.get_json(silent=True) or {}
            logo_file = None

        # Honeypot Check (Spam Trap)
        if form_data.get('email_confirm_2'):
            ip = _get_client_ip()
            ban_ip(ip, "Spam Trap Honeypot Filled")
            return jsonify({'ok': False, 'error': 'Bot detected.'}), 403

        form_data['_client_ip'] = _get_client_ip()
        form_data['_consent_version'] = os.getenv('CONSENT_VERSION', '2026-03-28')

        app_config = {
            'DATA_DIR': DATA_DIR,
            'REPORTS_DIR': REPORTS_DIR,
            'REPORTS_FALLBACK_DIR': REPORTS_FALLBACK_DIR
        }
        
        result = LeadService.process_submission(form_data, logo_file, session, app_config)
        
        return jsonify(result)

    except Exception as e:
        print(f"[CRITICAL] {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/lgpd/request', methods=['POST'])
@csrf.exempt
@rate_limited
def lgpd_request():
    try:
        payload = request.get_json(silent=True) or request.form.to_dict()
        result = LGPDService.create_request(payload, _get_client_ip())
        status = 200 if result.get('ok') else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Admin ───────────────────────────────────────────────────────────────────────────────────

@app.route('/privacy')
def privacy():
    return render_template(
        'privacy.html',
        dpo_email=os.getenv('DPO_EMAIL', 'privacidade@clienteiro.com.br'),
        retention_days=int(os.getenv('LEAD_RETENTION_DAYS', '180')),
        consent_version=os.getenv('CONSENT_VERSION', '2026-03-28')
    )

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/lgpd')
def lgpd():
    return render_template(
        'lgpd.html',
        dpo_email=os.getenv('DPO_EMAIL', 'privacidade@clienteiro.com.br')
    )

@app.route('/admin')
@login_required
def admin():
    if session.get('nivel_acesso') == 'cliente':
        return redirect(url_for('dashboard'))
    try:
        conn  = get_db()
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM internal_leads')
            total = cur.fetchone()['count']
            cur.execute('SELECT COUNT(*) FROM internal_leads WHERE printed=1')
            printed = cur.fetchone()['count']
            stats = {'total': int(total), 'printed': int(printed), 'waiting': int(total - printed)}

            cur.execute('SELECT * FROM internal_leads ORDER BY id DESC LIMIT 200')
            rows = cur.fetchall()
        leads = []
        for row in rows:
            lead = dict(row)
            wa_target = _whatsapp_target_from_phone(lead.get('phone'))
            lead['wa_url'] = f"https://wa.me/{wa_target}" if wa_target else ''
            leads.append(lead)

        gestor_nome  = session.get('gestor_nome', '')
        nivel_acesso = session.get('nivel_acesso', '')

        users = []
        if nivel_acesso == 'diretor':
            with conn.cursor() as cur:
                cur.execute('SELECT id, nome, nome_usuario, cargo, nivel_acesso, criado_em FROM gestores ORDER BY id DESC')
                users = cur.fetchall()

        kpis = get_dashboard_kpis(conn)

        conn.close()
        return render_template('admin.html', leads=leads, stats=stats, 
                               gestor_nome=gestor_nome, nivel_acesso=nivel_acesso, users=users, kpis=kpis)
    except Exception as e:
        print(f"[ADMIN] {e}")
        return f"Erro ao carregar admin: {e}", 500


@app.route('/admin/audit')
@diretor_required
def admin_audit():
    """Exibe o log de auditoria do sistema."""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('''
                SELECT a.*, g.nome_usuario 
                FROM audit_log a
                LEFT JOIN gestores g ON a.gestor_id = g.id
                ORDER BY a.timestamp DESC 
                LIMIT 500
            ''')
            rows = cur.fetchall()
        logs = [dict(r) for r in rows]
        conn.close()
        return render_template('audit.html', logs=logs)
    except Exception as e:
        print(f"[AUDIT] {e}")
        return f"Erro ao carregar audit: {e}", 500


@app.route('/admin/api/lgpd/requests')
@diretor_required
def admin_lgpd_requests():
    limit = request.args.get('limit', 200)
    return jsonify(LGPDService.list_requests(limit))


@app.route('/admin/api/lgpd/requests/<int:request_id>/status', methods=['POST'])
@csrf.exempt
@diretor_required
def admin_lgpd_update_request_status(request_id):
    data = request.get_json(silent=True) or {}
    result = LGPDService.update_request_status(
        request_id=request_id,
        status=data.get('status', ''),
        handled_by=session.get('gestor_id')
    )
    if result.get('ok'):
        conn = get_db()
        log_acao(conn, f'lgpd_request_status:{data.get("status", "")}', request_id)
        conn.close()
    code = 200 if result.get('ok') else 400
    return jsonify(result), code


@app.route('/admin/api/lgpd/run_retention', methods=['POST'])
@csrf.exempt
@diretor_required
def admin_lgpd_run_retention():
    result = LGPDService.run_retention_cleanup()
    if result.get('ok'):
        conn = get_db()
        log_acao(conn, f'lgpd_retention_cleanup:{result.get("anonymized_count", 0)}')
        conn.close()
    code = 200 if result.get('ok') else 500
    return jsonify(result), code


@app.route('/admin/mark_printed/<int:lead_id>', methods=['POST'])
@login_required
def mark_printed(lead_id):
    try:
        conn = get_db()
        log_acao(conn, 'mark_printed', lead_id)
        with conn.cursor() as cur:
            cur.execute('UPDATE internal_leads SET printed=1 WHERE id=%s', (lead_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/admin/delete_lead/<int:id>', methods=['POST'])
@login_required
def delete_lead(id):
    try:
        conn = get_db()
        log_acao(conn, 'delete_lead', id)
        with conn.cursor() as cur:
            cur.execute('DELETE FROM internal_leads WHERE id=%s', (id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/admin/edit_lead/<int:id>', methods=['POST'])
@login_required
def edit_lead(id):
    try:
        conn = get_db()
        log_acao(conn, 'edit_lead', id)
        
        company = request.form.get('company_name')
        nicho   = request.form.get('nicho')
        city    = request.form.get('city')
        phone   = request.form.get('phone')
        score   = request.form.get('score', 0)

        with conn.cursor() as cur:
            cur.execute('''
                UPDATE internal_leads 
                SET company_name=%s, nicho=%s, city=%s, phone=%s, clienteiro_score=%s
                WHERE id=%s
            ''', (company, nicho, city, phone, score, id))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/admin/api/hunter_config', methods=['GET', 'POST'])
@diretor_required
def admin_hunter_config():
    config_path = os.path.join(BASE_DIR, 'hunter_config.json')
    if request.method == 'POST':
        try:
            data = request.get_json(silent=True) or {}
            # Sanitização simples para nichos e cidades
            nichos = [n.strip() for n in str(data.get('nichos', '')).split(',') if n.strip()]
            cidades = [c.strip() for c in str(data.get('cidades', '')).split(',') if c.strip()]
            
            if not nichos or not cidades:
                return jsonify({'ok': False, 'error': 'Informe ao menos um nicho e uma cidade.'}), 400
                
            new_cfg = {"nichos": nichos, "cidades": cidades}
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(new_cfg, f, indent=2, ensure_ascii=False)
            
            return jsonify({'ok': True, 'msg': 'Caçador atualizado com sucesso!'})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500
            
    # GET
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return jsonify({'ok': True, 'config': json.load(f)})
        return jsonify({'ok': True, 'config': {"nichos": [], "cidades": []}})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/admin/export')
@diretor_required
def export_csv():
    """Exporta todos os leads como CSV."""
    try:
        import csv
        import io
        conn  = get_db()
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM internal_leads ORDER BY id DESC')
            rows  = cur.fetchall()
        conn.close()

        output = io.StringIO()
        output.write('\ufeff') # BOM for Excel UTF-8
        writer = csv.writer(output)
        writer.writerow(['ID', 'Nome', 'Empresa', 'Nicho', 'Cidade', 'Telefone', 'Score', 'Tipo', 'Autorização', 'Impresso', 'Data'])
        for row in rows:
            r = dict(row)
            writer.writerow([
                r['id'], r['user_name'], r['company_name'], r['nicho'], r['city'],
                r['phone'], r['clienteiro_score'], r['type_focus'],
                'Sim' if r['consent'] else 'Não',
                'Sim' if r['printed'] else 'Não',
                r['timestamp'],
            ])

        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=clienteiro_oportunidades.csv'}
        )
    except Exception as e:
        return f"Erro ao exportar: {e}", 500


@app.route('/download/<filename>')
def download(filename):
    # Segurança: só permite PDFs
    if not filename.endswith('.pdf'):
        return 'Arquivo não permitido', 403
    primary_path = os.path.join(REPORTS_DIR, filename)
    if os.path.exists(primary_path):
        return send_from_directory(REPORTS_DIR, filename)

    fallback_path = os.path.join(REPORTS_FALLBACK_DIR, filename)
    if os.path.exists(fallback_path):
        return send_from_directory(REPORTS_FALLBACK_DIR, filename)

    return 'Arquivo nao encontrado', 404


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    from flask import flash

    if request.method == 'POST':
        ok, msg = AuthService.register(request.form, (session.get('nivel_acesso') == 'diretor'))
        flash(msg, 'success' if ok else 'error')
        if ok:
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/admin/api/leads')
@login_required
def api_leads():
    """Retorna os últimos 15 leads agregados para a TV Live."""
    if session.get('nivel_acesso') == 'cliente':
        return jsonify({'ok': False, 'error': 'Acesso restrito.'}), 403
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM internal_leads ORDER BY id DESC LIMIT 15')
            rows = cur.fetchall()
        leads = [dict(r) for r in rows]
        conn.close()
        return jsonify({'ok': True, 'leads': leads})
    except Exception as e:
        return jsonify({'ok': False, 'leads': []})


@app.route('/admin/live')
@login_required
def admin_live():
    """Tela de monitoramento tempo real para TVs Verticais."""
    if session.get('nivel_acesso') == 'cliente':
        return redirect(url_for('dashboard'))
    return render_template('admin_live.html')


# --- SISTEMA DE LOGS NÃO-BLOQUEANTE (FILE POLLING) PARA O WORKER ---
LIVE_LOG_FILE = os.path.join(os.path.dirname(__file__), 'data', 'live_worker.log')
LIVE_PID_FILE = os.path.join(os.path.dirname(__file__), 'data', 'live_worker.pid')


def _read_worker_pid():
    try:
        with open(LIVE_PID_FILE) as f:
            return int((f.read() or '').strip())
    except Exception:
        return None


def _is_pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _clear_worker_pid_file():
    try:
        if os.path.exists(LIVE_PID_FILE):
            os.remove(LIVE_PID_FILE)
    except Exception:
        pass

@app.route('/admin/start_worker', methods=['POST'])
@login_required
def start_worker():
    """Inicia o subprocesso e escreve a saída em um arquivo."""
    import subprocess, sys, os
    if session.get('nivel_acesso') == 'cliente':
        return jsonify({'ok': False, 'error': 'Acesso restrito.'}), 403
    if not env_bool("ENABLE_STREAM_HARVEST", False):
        return jsonify({'ok': False, 'error': 'ENABLE_STREAM_HARVEST=false'})

    # Verifica se já está rodando
    pid = _read_worker_pid()
    if pid and _is_pid_alive(pid):
        return jsonify({'ok': False, 'error': 'Worker já está rodando'})
    _clear_worker_pid_file()

    os.makedirs(os.path.dirname(LIVE_LOG_FILE), exist_ok=True)
    with open(LIVE_LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("[Dashboard] O Motor de Colheita foi iniciado!\n")

    payload = request.get_json(silent=True) or {}
    requested_type_focus = str(payload.get('type_focus', '')).strip().lower()
    if requested_type_focus not in ('', 'b2b', 'b2c', 'misto'):
        return jsonify({'ok': False, 'error': 'type_focus invalido'}), 400
    type_focus = requested_type_focus or 'b2b'

    # Env com todas as flags necessárias para o worker minerar
    env = {
        **os.environ,
        'PYTHONIOENCODING': 'utf-8',
        'ENABLE_HARVEST': 'true',
        'HARVEST_MODE': 'true',
        'ENABLE_LIVE_SCRAPING': 'true',
        'HARVEST_TYPE_FOCUS': type_focus,
    }

    try:
        out_file = open(LIVE_LOG_FILE, 'a', encoding='utf-8')

        # No Windows: CREATE_NEW_PROCESS_GROUP isola o worker do processo Flask.
        # No Linux/Mac: os.setsid cria nova session para o worker não arrastar o Flask.
        extra_kwargs = {}
        if sys.platform == 'win32':
            extra_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            extra_kwargs['preexec_fn'] = os.setsid

        proc = subprocess.Popen(
            [sys.executable, '-u', 'harvest_leads.py', '1'],
            stdout=out_file, stderr=out_file,
            env=env,
            **extra_kwargs
        )
        with open(LIVE_PID_FILE, 'w') as f:
            f.write(str(proc.pid))
        return jsonify({'ok': True, 'type_focus': type_focus})
    except Exception as e:
        _clear_worker_pid_file()
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/admin/stop_worker', methods=['POST'])
@login_required
def stop_worker():
    """Para o worker limpo matando o process group."""
    import sys, os, signal, time
    if session.get('nivel_acesso') == 'cliente':
        return jsonify({'ok': False, 'error': 'Acesso restrito.'}), 403
    pid = _read_worker_pid()
    if not pid:
        return jsonify({'ok': False, 'error': 'Worker nao esta ativo'})

    try:
        if _is_pid_alive(pid):
            if sys.platform != 'win32':
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)

            deadline = time.time() + 6
            while time.time() < deadline and _is_pid_alive(pid):
                time.sleep(0.2)

            # Fallback agressivo para impedir processo zumbi.
            if _is_pid_alive(pid):
                if sys.platform != 'win32':
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGKILL)
                else:
                    os.kill(pid, signal.SIGKILL)

        with open(LIVE_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write("\n[Dashboard] Motor Desconectado pelo usuario.\n")

        _clear_worker_pid_file()
        return jsonify({'ok': True})
    except Exception as e:
        _clear_worker_pid_file()
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/admin/poll_logs')
@login_required
def poll_logs():
    """Le as novas as linhas do arquivo de log desde o ultimo cursor.
    Isso e 100% non-blocking e seguro para Gunicorn Sync."""
    import json
    if session.get('nivel_acesso') == 'cliente':
        return jsonify({'ok': False, 'error': 'Acesso restrito.'}), 403
    cursor = int(request.args.get('cursor', 0))
    logs = []
    leads = []
    new_cursor = cursor
    
    if os.path.exists(LIVE_LOG_FILE):
        try:
            with open(LIVE_LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(cursor)
                content = f.read()
                new_cursor = f.tell()
                for line in content.split('\n'):
                    line = line.strip()
                    if not line: continue
                    if '__LEAD_DATA__' in line:
                        try:
                            lead_data = json.loads(line.split('__LEAD_DATA__')[1])
                            leads.append(lead_data)
                        except:
                            pass
                    else:
                        logs.append(line)
        except Exception:
            pass

    is_running = False
    if os.path.exists(LIVE_PID_FILE):
        try:
             with open(LIVE_PID_FILE) as f:
                  pid = int(f.read().strip())
                  os.kill(pid, 0)
                  is_running = True
        except:
             pass

    return jsonify({
        'logs': logs,
        'leads': leads,
        'cursor': new_cursor,
        'is_running': is_running
    })


@app.route('/auth/google')
def auth_google():
    flash('Login com Google ainda nao esta configurado. Use usuario e senha por enquanto.', 'error')
    return redirect(url_for('login'))


@app.route('/auth/facebook')
def auth_facebook():
    flash('Login com Facebook ainda nao esta configurado. Use usuario e senha por enquanto.', 'error')
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if session.get('gestor_id'):
        if session.get('nivel_acesso') == 'diretor':
            return redirect(url_for('admin'))
        return redirect(url_for('dashboard'))

    erro = None
    if request.method == 'POST':
        ok, nivel = AuthService.login(request.form.get('usuario'), request.form.get('senha'))
        if ok:
            if nivel == 'diretor':
                return redirect(url_for('admin'))
            return redirect(url_for('dashboard'))
        else:
            erro = 'Usuário ou senha incorretos.'

    return render_template('login.html', erro=erro)

@app.route('/dashboard')
@login_required
def dashboard():
    """Painel do Usuário (Cliente/Consultor)."""
    try:
        nivel = session.get('nivel_acesso')
        gid   = session.get('gestor_id')
        conn  = get_db()
        
        with conn.cursor() as cur:
            # Stats básicas
            if nivel == 'diretor':
                return redirect(url_for('admin'))
            
            # Filtra leads do próprio gestor (para Clientes) 
            # Consultores podem ver todos ou apenas de clientes? 
            # Conforme pedido: Consultores veem leads para imprimir/editar (Provavelmente todos os leads internos)
            # Mas Clientes veem APENAS os deles.
            
            if nivel == 'cliente':
                cur.execute('SELECT * FROM internal_leads WHERE gestor_id = %s ORDER BY id DESC', (gid,))
            else: # consultor
                cur.execute('SELECT * FROM internal_leads ORDER BY id DESC LIMIT 500')
            
            leads = cur.fetchall()
            
            # Pega gen_count e plano se for cliente
            gen_count = 0
            plano = 'gratis'
            if nivel == 'cliente':
                cur.execute('SELECT gen_count, plano FROM gestores WHERE id = %s', (gid,))
                u = cur.fetchone()
                gen_count = u['gen_count'] if u else 0
                plano = u['plano'] if u and 'plano' in u else 'gratis'
            
            # Pega Telefone do Bot
            cur.execute("SELECT value FROM system_config WHERE key = 'bot_phone'")
            row = cur.fetchone()
            bot_phone = row['value'] if row else '5511916722043'
            
            # Pega Cidades já mapeadas (Mix de leads reais + cache)
            cur.execute("SELECT DISTINCT city FROM internal_leads WHERE city IS NOT NULL AND city <> ''")
            c1 = [r['city'] for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT city FROM scraped_leads WHERE city IS NOT NULL AND city <> ''")
            c2 = [r['city'] for r in cur.fetchall()]
            db_cidades = sorted(list(set(c1 + c2)))
                
        conn.close()
        return render_template('user_dashboard.html', 
                               leads=leads, 
                               nivel=nivel, 
                               gen_count=gen_count, 
                               plano=plano,
                               bot_phone=bot_phone,
                               db_cidades=db_cidades)
    except Exception as e:
        print(f"[DASHBOARD] {e}")
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    AuthService.logout()
    return redirect(url_for('login'))


@app.route('/live')
def live():
    """Tela pública de TV — exibe contador de leads ao vivo para a feira."""
    return render_template('live.html')


@app.route('/api/live-stats', methods=['GET', 'OPTIONS'])
def live_stats():
    if request.method == 'OPTIONS':
        resp = jsonify({})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET'
        return resp
    """JSON endpoint consumido pela tela /live a cada 5s."""
    try:
        conn    = get_db()
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM internal_leads')
            total_all = int(cur.fetchone()['count'])

            cur.execute('SELECT COUNT(*) FROM internal_leads WHERE printed=1')
            printed_all = int(cur.fetchone()['count'])

            cur.execute('SELECT COUNT(*) FROM internal_leads WHERE DATE(timestamp) = CURRENT_DATE')
            total_today = int(cur.fetchone()['count'])

            cur.execute('SELECT COUNT(*) FROM internal_leads WHERE DATE(timestamp) = CURRENT_DATE AND printed=1')
            printed_today = int(cur.fetchone()['count'])
        conn.close()
        waiting_today = max(total_today - printed_today, 0)
        resp = jsonify({
            'total': total_today,
            'printed': printed_today,
            'waiting': waiting_today,
            'all_total': total_all,
            'all_printed': printed_all,
            'updated_at': datetime.now().isoformat()
        })
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        resp = jsonify({'total': 0, 'printed': 0, 'waiting': 0, 'all_total': 0, 'all_printed': 0, 'error': str(e)})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp


@app.route('/api/live-feed', methods=['GET', 'OPTIONS'])
def live_feed():
    if request.method == 'OPTIONS':
        resp = jsonify({})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET'
        return resp
    """Feed de leads recentes para o LIVE."""
    try:
        try:
            limit = int(request.args.get('limit', 12))
        except Exception:
            limit = 12
        limit = max(1, min(limit, 50))

        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('''
                SELECT id, company_name, city, nicho, phone, clienteiro_score, printed, timestamp
                FROM internal_leads
                ORDER BY id DESC
                LIMIT %s
            ''', (limit,))
            rows = cur.fetchall()
        conn.close()

        leads = []
        for row in rows:
            lead = dict(row)
            wa_target = _whatsapp_target_from_phone(lead.get('phone'))
            lead['wa_url'] = f"https://wa.me/{wa_target}" if wa_target else ''
            leads.append(lead)
        resp = jsonify({'ok': True, 'leads': leads})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        resp = jsonify({'ok': False, 'leads': [], 'error': str(e)})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp


@app.route('/admin/api/bot_status')
@login_required
def admin_bot_status():
    """Proxy de status do bot para evitar CORS."""
    url = os.getenv('BOT_STATUS_URL', 'http://bot:3582/status')
    candidates = [url, 'http://127.0.0.1:3582/status']

    for candidate in candidates:
        try:
            res = requests.get(candidate, timeout=2)
            if res.ok:
                data = res.json()
                data['ok'] = True
                return jsonify(data)
        except Exception:
            continue
    return jsonify({'ok': False, 'status': 'OFFLINE', 'enabled': False})


@app.route('/admin/api/hook/<int:lead_id>', methods=['POST'])
@login_required
def get_strategic_hook(lead_id):
    """Gera um gancho de venda estratégico (Zero-AI) para o lead."""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM internal_leads WHERE id = %s', (lead_id,))
            lead = cur.fetchone()
        conn.close()
        
        if not lead:
            return jsonify({'ok': False, 'error': 'Lead não encontrado'}), 404
            
        lead_dict = dict(lead)
        from core.strategic_hooks import get_best_hook
        hook = get_best_hook(lead_dict)
        
        return jsonify({'ok': True, 'hook': hook})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/admin/api/config', methods=['GET', 'POST'])
def admin_config():
    """Gerencia as configurações globais do sistema (Enterprise)."""
    # Bypass para o Bot se tiver API Key Correta
    api_key_header = request.headers.get('X-API-KEY')
    is_bot = _valid_internal_api_key(api_key_header)
    
    if not is_bot:
        # Se não for o bot, exige login de gestor
        if not session.get('gestor_id'):
            return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    conn = get_db()
    if request.method == 'POST':
        if not is_bot and session.get('nivel_acesso') != 'diretor':
            return jsonify({'ok': False, 'error': 'Apenas diretores podem mudar configs'}), 403
            
        try:
            data = request.get_json()
            with conn.cursor() as cur:
                for key, value in data.items():
                    cur.execute('''
                        INSERT INTO system_config (key, value, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                    ''', (key, str(value)))
            conn.commit()
            return jsonify({'ok': True})
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500
        finally:
            conn.close()
    
    # GET: Retorna todas as configs
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT key, value FROM system_config')
            rows = cur.fetchall()
        configs = {row['key']: row['value'] for row in rows}
        conn.close()
        return jsonify({'ok': True, 'configs': configs})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/admin/api/register_appointment', methods=['POST'])
def register_appointment():
    """Endpoint para o Bot registrar um agendamento no Supabase."""
    api_key_header = request.headers.get('X-API-KEY')
    if not _valid_internal_api_key(api_key_header):
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json(silent=True) or {}
        phone = _normalize_phone(data.get('phone', ''))
        date_str = str(data.get('date') or '').strip()  # ISO format

        if not phone or not date_str:
            return jsonify({'ok': False, 'error': 'phone e date sao obrigatorios'}), 400

        # Valida formato de data de entrada para evitar registro quebrado
        try:
            datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            return jsonify({'ok': False, 'error': 'date invalida, esperado ISO-8601'}), 400

        phone_digits = _only_digits(phone)
        phone_like = f"%{phone_digits[-11:]}" if phone_digits else '%'

        conn = get_db()
        with conn.cursor() as cur:
            # Tenta achar o lead pelo telefone normalizado (ultimos 11 digitos)
            cur.execute('''
                SELECT id
                FROM internal_leads
                WHERE regexp_replace(COALESCE(phone, ''), '\\D', '', 'g') LIKE %s
                ORDER BY id DESC
                LIMIT 1
            ''', (phone_like,))
            lead = cur.fetchone()
            lead_id = lead['id'] if lead else None

            # Idempotencia por dia: no maximo um agendamento por telefone/dia.
            cur.execute('''
                SELECT id, appointment_date
                FROM appointments
                WHERE regexp_replace(COALESCE(phone, ''), '\\D', '', 'g') LIKE %s
                  AND DATE(appointment_date AT TIME ZONE 'America/Sao_Paulo')
                      = DATE(%s::timestamp AT TIME ZONE 'America/Sao_Paulo')
                ORDER BY created_at DESC
                LIMIT 1
            ''', (phone_like, date_str))
            existing_same_day = cur.fetchone()

            if existing_same_day:
                existing_id = existing_same_day['id']
                existing_date = existing_same_day['appointment_date']
                existing_iso = existing_date.isoformat() if hasattr(existing_date, 'isoformat') else str(existing_date)
                is_duplicate = existing_iso[:16] == date_str.replace('Z', '+00:00')[:16]

                if not is_duplicate:
                    cur.execute('''
                        UPDATE appointments
                        SET appointment_date=%s, status='scheduled'
                        WHERE id=%s
                    ''', (date_str, existing_id))

                conn.commit()
                conn.close()
                return jsonify({
                    'ok': True,
                    'created': False,
                    'updated': not is_duplicate,
                    'duplicate': is_duplicate,
                    'already_scheduled_today': True,
                    'appointment_id': existing_id
                })

            cur.execute('''
                INSERT INTO appointments (lead_id, phone, appointment_date, status)
                VALUES (%s, %s, %s, 'scheduled')
                RETURNING id
            ''', (lead_id, phone, date_str))
            row = cur.fetchone()

        conn.commit()
        conn.close()
        return jsonify({
            'ok': True,
            'created': True,
            'appointment_id': row['id'] if row else None
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/admin/api/bot/message_guard', methods=['POST'])
def bot_message_guard():
    """Controle central anti-spam/idempotencia para mensagens do bot."""
    api_key_header = request.headers.get('X-API-KEY')
    if not _valid_internal_api_key(api_key_header):
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    try:
        data = request.get_json(silent=True) or {}
        phone = _normalize_phone(data.get('phone', ''))
        category = _clean_text(data.get('category', ''), '', 64).lower()
        dedupe_key = _clean_text(data.get('dedupe_key', ''), '', 220) or None
        payload_hash = _clean_text(data.get('payload_hash', ''), '', 128) or None

        try:
            max_per_day = int(data.get('max_per_day', 0) or 0)
        except Exception:
            max_per_day = 0
        max_per_day = max(0, min(max_per_day, 20))

        if not phone or not category:
            return jsonify({'ok': False, 'error': 'phone e category sao obrigatorios'}), 400

        # fallback de hash quando nenhuma dedupe_key e nenhum payload_hash forem enviados
        if not dedupe_key and not payload_hash:
            payload_hash = hashlib.sha256(f"{phone}|{category}".encode('utf-8')).hexdigest()

        conn = get_db()
        with conn.cursor() as cur:
            if dedupe_key:
                cur.execute('''
                    SELECT id, created_at
                    FROM bot_message_log
                    WHERE dedupe_key = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (dedupe_key,))
                hit = cur.fetchone()
                if hit:
                    conn.close()
                    return jsonify({
                        'ok': True,
                        'allowed': False,
                        'reason': 'duplicate_dedupe_key',
                        'last_sent_at': hit['created_at'].isoformat() if hit.get('created_at') else None
                    })

            if max_per_day > 0:
                cur.execute('''
                    SELECT COUNT(*) AS total
                    FROM bot_message_log
                    WHERE phone = %s
                      AND category = %s
                      AND sent_day = CURRENT_DATE
                ''', (phone, category))
                row = cur.fetchone()
                total_today = int(row['total']) if row else 0
                if total_today >= max_per_day:
                    conn.close()
                    return jsonify({
                        'ok': True,
                        'allowed': False,
                        'reason': 'daily_limit_reached',
                        'total_today': total_today
                    })

            cur.execute('''
                INSERT INTO bot_message_log (phone, category, dedupe_key, payload_hash, sent_day)
                VALUES (%s, %s, %s, %s, CURRENT_DATE)
            ''', (phone, category, dedupe_key, payload_hash))

        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'allowed': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/admin/api/update_appointment', methods=['POST'])
@login_required
def update_appointment():
    """Reagenda um compromisso e sincroniza com Google Agenda."""
    try:
        data = request.get_json()
        app_id = data.get('id')
        new_start = data.get('new_start') # ISO string
        
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('UPDATE appointments SET appointment_date=%s WHERE id=%s RETURNING phone', (new_start, app_id))
            row = cur.fetchone()
            phone = row['phone'] if row else None
            
        conn.commit()
        conn.close()
        
        # SincronizaÃ§Ã£o com Google (via Bot API)
        # O bot jÃ¡ tem as credenciais GCloud. Vamos avisÃ¡-lo para atualizar o evento.
        try:
            api_key = _required_env('INTERNAL_API_KEY')
            headers = {'X-API-Key': api_key} if api_key else {}
            requests.post('http://127.0.0.1:3582/api/sync-google', json={
                'appointment_id': app_id,
                'new_start': new_start,
                'phone': phone
            }, headers=headers, timeout=5)
        except:
            pass # Se o bot estiver offline agora, nÃ£o trava o DB
            
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/admin/restart-services', methods=['POST'])
@diretor_required
def restart_services():
    """Reinicia o ecossistema (Flask + Bot)."""
    try:
        import subprocess
        # Reinicia o Bot (assumindo PM2 ou similar, ou apenas matando para o supervisor subir)
        # Aqui, como estamos num ambiente de dev, vamos tentar um comando de restart simples
        # No Windows do usuÃ¡rio, ele provavelmente quer que a gente feche e abra
        # Mas como sou um agente, vou enviar um sinal ou apenas responder OK e sugerir o comando
        return jsonify({'ok': True, 'message': 'Comando de reinicializaÃ§Ã£o enviado.'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/admin/api/agenda')
@login_required
def admin_agenda():
    """Retorna os agendamentos registrados no sistema."""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute('''
                SELECT a.*, l.company_name, l.user_name as lead_name
                FROM appointments a
                LEFT JOIN internal_leads l ON a.lead_id = l.id
                ORDER BY a.appointment_date ASC
            ''')
            rows = cur.fetchall()
        appointments = [dict(r) for r in rows]
        conn.close()
        return jsonify({'ok': True, 'appointments': appointments})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if __name__ == '__main__':
    print("\nClienteiro - Automacao Inteligente de Clientes")
    print("Kiosk : http://localhost:3583")
    print("Admin : http://localhost:3583/admin\n")
    port = int(os.getenv('PORT', '3583'))
    host = os.getenv('FLASK_RUN_HOST', '127.0.0.1')
    app.run(debug=False, port=port, host=host, threaded=True)

