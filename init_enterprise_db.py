import os

from core.db_manager import get_db_connection

def update_enterprise_schema():
    print("🚀 Atualizando esquema para Versão Enterprise...")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Tabela de Configurações do Bot
            cur.execute('''
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 2. Inserir valores padrão se não existirem
            internal_api_key = os.getenv('INTERNAL_API_KEY', '').strip()
            configs = [
                ('admin_phones', '5511999999999'),
                ('google_calendar_id', 'primary'),
                ('bot_status', 'OFFLINE'),
            ]
            if internal_api_key:
                configs.append(('internal_api_key', internal_api_key))
            for key, val in configs:
                cur.execute('''
                    INSERT INTO system_config (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO NOTHING
                ''', (key, val))
            
            # 3. Tabela de Agendamentos (Appointments)
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

            # 4. Log de mensagens do bot para anti-spam/idempotencia
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
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bot_message_log_phone_category_day ON bot_message_log (phone, category, sent_day)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bot_message_log_dedupe_key ON bot_message_log (dedupe_key)")
            
            print("✅ Tabelas 'system_config', 'appointments' e 'bot_message_log' verificadas/criadas.")
            conn.commit()
    except Exception as e:
        print(f"❌ Erro ao atualizar esquema: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    update_enterprise_schema()
