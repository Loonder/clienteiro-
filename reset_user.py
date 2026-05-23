from core.db_manager import get_db_connection
import os
from dotenv import load_dotenv

load_dotenv()

def reset_limit():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Reseta o contador de todos os gestores ou de um específico
            print("Resetando contadores de geração de leads...")
            cur.execute("UPDATE gestores SET gen_count = 0")
            conn.commit()
            print("Contadores resetados com sucesso para todos os usuários.")
    except Exception as e:
        print(f"Erro ao resetar: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    reset_limit()
