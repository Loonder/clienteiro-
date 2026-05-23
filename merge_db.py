import sqlite3
import sys
import os

def merge_dbs(main_db_path, source_db_path):
    if not os.path.exists(source_db_path):
        print(f"❌ Arquivo de origem não encontrado: {source_db_path}")
        return

    print(f"🔗 Conectando ao Banco Principal: {main_db_path}")
    print(f"📂 Lendo dados de: {source_db_path}")

    try:
        conn_main = sqlite3.connect(main_db_path)
        conn_src = sqlite3.connect(source_db_path)

        # 1. Garante que a tabela de cache existe no principal
        conn_main.execute('''
            CREATE TABLE IF NOT EXISTS scraped_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nicho TEXT, city TEXT, type_focus TEXT,
                name TEXT, phone TEXT, rating REAL, source TEXT UNIQUE,
                criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn_main.commit()

        # 2. Extrai dados do banco secundário
        cursor = conn_src.execute("SELECT nicho, city, type_focus, name, phone, rating, source FROM scraped_leads")
        rows = cursor.fetchall()
        
        print(f"📊 Encontrados {len(rows)} leads na origem.")

        inserted = 0
        for r in rows:
            try:
                # INSERT OR IGNORE evita duplicidade de URLs (source UNIQUE)
                conn_main.execute('''
                    INSERT OR IGNORE INTO scraped_leads 
                    (nicho, city, type_focus, name, phone, rating, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', r)
                if conn_main.total_changes > 0:
                    inserted += 1
            except Exception:
                pass

        conn_main.commit()
        print(f"✅ Mesclagem Concluída! +{inserted} novos leads únicos inseridos.")

        conn_main.close()
        conn_src.close()

    except Exception as e:
        print(f"❌ Erro durante a mesclagem: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("\n📌 Uso: python merge_db.py <database_principal.sqlite> <database_auxiliar.sqlite>")
        sys.exit(1)
        
    merge_dbs(sys.argv[1], sys.argv[2])
