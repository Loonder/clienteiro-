from core.db_manager import get_db_connection
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    print("Iniciando migração: Adicionando coluna 'slug'...")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Verifica se a coluna slug já existe
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'internal_leads' AND column_name = 'slug'")
            if not cur.fetchone():
                print("Adicionando coluna 'slug' em 'internal_leads'...")
                cur.execute("ALTER TABLE internal_leads ADD COLUMN slug VARCHAR(255)")
                conn.commit()
                print("Coluna 'slug' adicionada com sucesso.")
            else:
                print("Coluna 'slug' já existe.")
        
        # Aproveita para garantir que outras colunas necessárias existam
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'internal_leads' AND column_name = 'gestor_id'")
            if not cur.fetchone():
                print("Adicionando coluna 'gestor_id' em 'internal_leads'...")
                cur.execute("ALTER TABLE internal_leads ADD COLUMN gestor_id INTEGER")
                conn.commit()
                print("Coluna 'gestor_id' adicionada.")
                
    except Exception as e:
        print(f"Erro na migração: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
