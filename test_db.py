"""Utilitario manual para validar a conexao PostgreSQL configurada localmente.

Nao e teste automatizado do pytest. Use:
    python test_db.py
"""

import os

import psycopg2

__test__ = False


def check_conn(url):
    if not url:
        print("SUPABASE_DB_URL/DATABASE_URL nao configurada.")
        return

    try:
        conn = psycopg2.connect(url)
        print("Conexao OK.")
        conn.close()
    except Exception as exc:
        print("Falha ao conectar:", exc)


if __name__ == "__main__":
    check_conn(os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL"))
