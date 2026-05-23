import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
DB_URL = os.getenv('SUPABASE_DB_URL')

def migrate():
    print("🚀 Starting Database Migration...")
    conn = psycopg2.connect(DB_URL, sslmode='require')
    cur = conn.cursor()
    
    # 1. Add gen_count to gestores
    print("📦 Adding 'gen_count' to 'gestores'...")
    try:
        cur.execute("ALTER TABLE gestores ADD COLUMN IF NOT EXISTS gen_count INTEGER DEFAULT 0;")
        print("✅ Column 'gen_count' added successfully.")
    except Exception as e:
        print(f"❌ Error adding 'gen_count': {e}")
        conn.rollback()

    # 2. Add gestor_id to internal_leads (if not exists)
    print("📦 Ensuring 'gestor_id' in 'internal_leads'...")
    try:
        cur.execute("ALTER TABLE internal_leads ADD COLUMN IF NOT EXISTS gestor_id INTEGER;")
        print("✅ Column 'gestor_id' checked/added successfully.")
    except Exception as e:
        print(f"❌ Error adding 'gestor_id': {e}")
        conn.rollback()

    conn.commit()
    cur.close()
    conn.close()
    print("🏁 Migration Finished!")

if __name__ == "__main__":
    migrate()
