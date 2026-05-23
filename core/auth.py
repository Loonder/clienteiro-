import os
from functools import wraps
from flask import session, redirect, url_for, request, current_app
from werkzeug.routing import BuildError
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------------------------------------------------------------------
# Utilitários de senha
# ---------------------------------------------------------------------------

def hash_password(password):
    """Gera hash seguro para senha (Werkzeug)."""
    return generate_password_hash(password)


def check_password(password, pw_hash):
    if not pw_hash:
        return False
    return check_password_hash(pw_hash, password)


def _login_redirect():
    """
    Redireciona para o endpoint login quando existir.
    Em apps de teste minimalistas, faz fallback para /login.
    """
    try:
        if current_app and 'login' in current_app.view_functions:
            return redirect(url_for('login'))
    except BuildError:
        pass
    return redirect('/login')


# ---------------------------------------------------------------------------
# Decorators de autenticação e autorização
# ---------------------------------------------------------------------------

def login_required(f):
    """Redireciona para /login se não houver sessão ativa."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('gestor_id'):
            return _login_redirect()
        return f(*args, **kwargs)
    return decorated


def diretor_required(f):
    """Permite acesso apenas para gestores com nível 'diretor'."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('gestor_id'):
            return _login_redirect()
        if session.get('nivel_acesso') != 'diretor':
            return "Acesso restrito ao Diretor.", 403
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Seed: cria gestor padrão se o banco estiver vazio
# ---------------------------------------------------------------------------

def seed_default_gestor(conn):
    """
    Bootstrap de segurança: Cria os gestores padrões apenas se não existirem.
    Permite remover as senhas do .env após o primeiro boot bem sucedido.
    """
    try:
        cur = conn.cursor()
        
        # 1. Verifica se já existem gestores cadastrados
        cur.execute('SELECT COUNT(*) FROM gestores')
        result = cur.fetchone()
        gestor_count = int(result['count'] if 'count' in result else list(result.values())[0])
        
        # Se já tivermos gestores, não forçamos o overwrite das senhas via ENV
        # Isso atende ao requisito de "Zero Trust" e remoção de segredos do ambiente
        if gestor_count > 0:
            print("[Auth] 🛡️ Base de gestores já populada. Ignorando bootstrap via ENV.")
            cur.close()
            return

        # 2. Administrador Padrão (Apenas se o banco estiver vazio)
        admin_user = os.getenv('DEFAULT_ADMIN_USER')
        admin_pass = os.getenv('DEFAULT_ADMIN_PASS')
        
        if admin_user and admin_pass:
            admin_hash = hash_password(admin_pass)
            cur.execute('''
                INSERT INTO gestores (nome_usuario, senha_hash, nome, cargo, nivel_acesso)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (nome_usuario) DO NOTHING
            ''', (admin_user, admin_hash, 'Administrador do Sistema', 'Diretor', 'diretor'))
            print(f"[Seed] ✅ Usuário ADMIN '{admin_user}' provisionado.")

        # 3. Consultor Padrão 
        cons_user = os.getenv('DEFAULT_CONSULTOR_USER')
        cons_pass = os.getenv('DEFAULT_CONSULTOR_PASS')
        
        if cons_user and cons_pass:
            cons_hash = hash_password(cons_pass)
            cur.execute('''
                INSERT INTO gestores (nome_usuario, senha_hash, nome, cargo, nivel_acesso)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (nome_usuario) DO NOTHING
            ''', (cons_user, cons_hash, 'Consultor Padrão', 'Consultoria', 'consultor'))
            print(f"[Seed] ✅ Usuário CONSULTOR '{cons_user}' provisionado.")

        conn.commit()
        cur.close()
    except Exception as e:
        print(f"[Auth] ⚠️ Erro no bootstrap: {e}")


# ---------------------------------------------------------------------------
# Registro de ações no audit log
# ---------------------------------------------------------------------------

def log_acao(conn, acao: str, lead_id: int = None):
    """Registra ação do gestor logado no audit_log."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (gestor_id, acao, lead_id, ip) VALUES (%s, %s, %s, %s)",
                (session.get('gestor_id'), acao, lead_id, request.remote_addr)
            )
        conn.commit()
    except Exception as e:
        print(f"[Auth] Erro ao registrar ação: {e}")
