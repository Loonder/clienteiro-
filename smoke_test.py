import os
import sys
import subprocess
import requests
import time

def check_env():
    print("🔍 Verificando ambiente...")
    if not os.path.exists('.env'):
        print("❌ ERRO: Arquivo .env não encontrado.")
        return False
    print("✅ .env encontrado.")
    return True

def check_db():
    print("🔍 Verificando conexão com Supabase...")
    try:
        from core.db_manager import get_db_connection
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
        conn.close()
        print("✅ Conexão com Banco de Dados OK.")
        return True
    except Exception as e:
        print(f"❌ ERRO de Banco: {e}")
        return False

def check_dirs():
    print("🔍 Verificando diretórios vitais...")
    dirs = ['data', 'reports', 'static', 'templates', 'services', 'core']
    missing = [d for d in dirs if not os.path.exists(d)]
    if missing:
        print(f"❌ ERRO: Diretórios faltando: {missing}")
        return False
    print("✅ Estrutura de pastas OK.")
    return True

def run_flask_smoke():
    print("🔍 Testando inicialização do Flask (Smoke Test)...")
    # Tenta rodar o app por 3 segundos para ver se ele crasha no import
    process = subprocess.Popen([sys.executable, 'app.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3)
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        print(f"❌ ERRO: App falhou ao iniciar.\nStderr: {stderr.decode()}")
        return False
    process.terminate()
    print("✅ Inicialização básica do Flask OK.")
    return True

def main():
    print("=== 🧪 SMOKE TEST CLIENTEIRO ELITE ===\n")
    results = [
        check_env(),
        check_dirs(),
        check_db(),
        run_flask_smoke()
    ]
    
    if all(results):
        print("\n🚀 TUDO PERFEITO! O projeto está pronto para a VPS.")
    else:
        print("\n⚠️  ATENÇÃO: Foram encontrados problemas. Verifique os erros acima.")
        sys.exit(1)

if __name__ == "__main__":
    main()
