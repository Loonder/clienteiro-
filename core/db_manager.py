import os
from urllib.parse import unquote, urlparse

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def _get_db_url():
    return (
        os.getenv('SUPABASE_DB_URL')
        or os.getenv('DATABASE_URL')
        or os.getenv('POSTGRES_URL')
        or ''
    ).strip()


def _get_password_candidates(raw_password):
    if raw_password is None:
        return [None]
    # Always prefer the decoded password; trying encoded+decoded in sequence
    # can create extra failed auth attempts against Supabase Pooler.
    return [unquote(raw_password)]


def _raise_pooler_hint_if_needed(host, port, user, error):
    if not isinstance(error, OperationalError):
        raise error

    msg = str(error).lower()
    if "circuit breaker open" in msg and "authentication" in msg:
        raise RuntimeError(
            "Supabase Pooler bloqueou temporariamente por excesso de erros de autenticação "
            "(circuit breaker open). Pare o backend, aguarde alguns minutos sem novas tentativas "
            "e valide a URL/credenciais com um único teste antes de religar."
        ) from error

    if "password authentication failed" not in msg:
        raise error

    is_pooler = bool(host and "pooler.supabase.com" in host)
    looks_like_plain_postgres_user = bool(user and user == "postgres")
    port_is_suspicious = port in (None, 5432)

    if is_pooler and looks_like_plain_postgres_user and port_is_suspicious:
        raise RuntimeError(
            "Falha de autenticação no Supabase Pooler. A URL em runtime está no host "
            f"'{host}' com usuário '{user}' e porta '{port or 5432}'. "
            "Para Pooler, use usuário no formato 'postgres.<project-ref>' e porta 6543; "
            "ou troque para host direto 'db.<project-ref>.supabase.co:5432' com usuário 'postgres'."
        ) from error

    raise error


def get_db_connection():
    """Conexão resiliente: passa parâmetros explícitos para evitar erros de parsing em URLs complexas."""
    db_url = _get_db_url()
    if not db_url:
        raise ValueError("SUPABASE_DB_URL não configurada.")

    parsed = urlparse(db_url)
    
    # Extração robusta de parâmetros
    user = unquote(parsed.username) if parsed.username else 'postgres'
    password = unquote(parsed.password) if parsed.password else None
    host = parsed.hostname
    port = parsed.port or 5432
    dbname = parsed.path.lstrip('/') or 'postgres'

    return psycopg2.connect(
        user=user,
        password=password,
        host=host,
        port=port,
        dbname=dbname,
        sslmode='require',
        connect_timeout=10,
        cursor_factory=RealDictCursor
    )

def init_postgres_db():
    """Initializes the PostgreSQL database schema if it doesn't exist."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Leads Internos
    cur.execute('''
        CREATE TABLE IF NOT EXISTS internal_leads (
            id               SERIAL PRIMARY KEY,
            user_name        TEXT,
            company_name     TEXT,
            nicho            TEXT,
            city             TEXT,
            phone            TEXT,
            type_focus       TEXT,
            consent          INTEGER DEFAULT 0,
            consent_at       TIMESTAMP,
            consent_ip       TEXT,
            consent_version  TEXT,
            legal_basis      TEXT DEFAULT 'consent',
            clienteiro_score INTEGER DEFAULT 0,
            pdf_path         TEXT,
            printed          INTEGER DEFAULT 0,
            anonymized       INTEGER DEFAULT 0,
            retention_until  DATE,
            gestor_id        INTEGER,
            timestamp        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute("ALTER TABLE internal_leads ADD COLUMN IF NOT EXISTS consent_at TIMESTAMP")
    cur.execute("ALTER TABLE internal_leads ADD COLUMN IF NOT EXISTS consent_ip TEXT")
    cur.execute("ALTER TABLE internal_leads ADD COLUMN IF NOT EXISTS consent_version TEXT")
    cur.execute("ALTER TABLE internal_leads ADD COLUMN IF NOT EXISTS legal_basis TEXT DEFAULT 'consent'")
    cur.execute("ALTER TABLE internal_leads ADD COLUMN IF NOT EXISTS anonymized INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE internal_leads ADD COLUMN IF NOT EXISTS retention_until DATE")
    
    # 2. Gestores
    cur.execute('''
        CREATE TABLE IF NOT EXISTS gestores (
            id           SERIAL PRIMARY KEY,
            nome_usuario TEXT NOT NULL UNIQUE,
            senha_hash   TEXT NOT NULL,
            nome         TEXT,
            cargo        TEXT,
            nivel_acesso TEXT DEFAULT 'consultor',
            gen_count    INTEGER DEFAULT 0,
            criado_em    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute("ALTER TABLE gestores ADD COLUMN IF NOT EXISTS plano TEXT DEFAULT 'gratis'")

    
    # 3. Audit Log
    cur.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id        SERIAL PRIMARY KEY,
            gestor_id INTEGER REFERENCES gestores(id),
            acao      TEXT,
            lead_id   INTEGER,
            ip        TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Scraped Leads (Cache)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS scraped_leads (
            id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            nicho TEXT, 
            city TEXT, 
            type_focus TEXT,
            name TEXT, 
            phone TEXT, 
            rating REAL, 
            source TEXT UNIQUE,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. Configurações do Sistema
    cur.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 6. Interações de Leads
    cur.execute('''
        CREATE TABLE IF NOT EXISTS lead_interactions (
            id SERIAL PRIMARY KEY,
            lead_id INTEGER REFERENCES internal_leads(id) ON DELETE CASCADE,
            gestor_id INTEGER,
            action_type TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS lgpd_requests (
            id SERIAL PRIMARY KEY,
            protocol TEXT UNIQUE NOT NULL,
            requester_name TEXT NOT NULL,
            requester_phone TEXT,
            requester_email TEXT,
            request_type TEXT NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'recebido',
            ip TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            handled_at TIMESTAMP,
            handled_by INTEGER REFERENCES gestores(id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id SERIAL PRIMARY KEY,
            lead_id INTEGER REFERENCES internal_leads(id) ON DELETE CASCADE,
            phone TEXT NOT NULL,
            customer_name TEXT,
            appointment_date TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Compatibilidade com schemas legados que usavam coluna `date` em vez de `appointment_date`
    cur.execute('''
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'appointments'
                  AND column_name = 'date'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'appointments'
                  AND column_name = 'appointment_date'
            ) THEN
                ALTER TABLE appointments RENAME COLUMN date TO appointment_date;
            END IF;
        END
        $$;
    ''')

    # Garante colunas mínimas exigidas pelo app antes de índices/consultas
    cur.execute("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS appointment_date TIMESTAMP")
    cur.execute("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS customer_name TEXT")
    cur.execute("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'scheduled'")
    cur.execute("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS banned_ips (
            id SERIAL PRIMARY KEY,
            ip TEXT UNIQUE NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute("CREATE INDEX IF NOT EXISTS idx_banned_ips_ip ON banned_ips (ip)")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS bot_message_log (
            id SERIAL PRIMARY KEY,
            phone TEXT NOT NULL,
            category TEXT NOT NULL,
            dedupe_key TEXT,
            payload_hash TEXT,
            sent_day DATE DEFAULT CURRENT_DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute("CREATE INDEX IF NOT EXISTS idx_internal_leads_retention ON internal_leads (retention_until, anonymized)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_lgpd_requests_status ON lgpd_requests (status, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_appointments_phone_date ON appointments (phone, appointment_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bot_message_log_phone_category_day ON bot_message_log (phone, category, sent_day)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bot_message_log_dedupe_key ON bot_message_log (dedupe_key)")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS kiosk_roulette_claims (
            id SERIAL PRIMARY KEY,
            phone TEXT NOT NULL UNIQUE,
            user_name TEXT NOT NULL,
            won_prize TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            won_at TIMESTAMP
        )
    ''')
    cur.execute("CREATE INDEX IF NOT EXISTS idx_kiosk_roulette_phone ON kiosk_roulette_claims (phone)")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS roulette_webhook_queue (
            id SERIAL PRIMARY KEY,
            event_name TEXT NOT NULL,
            payload JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            next_retry_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute("CREATE INDEX IF NOT EXISTS idx_roulette_queue_status_retry ON roulette_webhook_queue (status, next_retry_at)")

    configs = [
        ('bot_phone', '5511916722043'),
        ('market_avg_score', '52'),
        ('kiosk_lock_seconds', '6')
    ]
    for k, v in configs:
        cur.execute("INSERT INTO system_config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (k, v))
    
    conn.commit()
    cur.close()
    conn.close()
    print("[Postgres] Tabelas e sementes verificadas.")

if __name__ == "__main__":
    try:
        init_postgres_db()
    except Exception as e:
        print(f"[Postgres] Erro: {e}")
