import os
from flask import session, flash
from core.auth import hash_password, check_password, seed_default_gestor
from core.db_manager import get_db_connection

class AuthService:
    @staticmethod
    def login(usuario, senha):
        """Validates credentials and sets up session."""
        usuario = str(usuario or '').strip().lower()
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM gestores WHERE nome_usuario = %s', (usuario,))
            gestor = cur.fetchone()
        conn.close()

        if gestor and check_password(senha, gestor['senha_hash']):
            session['gestor_id'] = gestor['id']
            session['gestor_nome'] = gestor['nome']
            session['nivel_acesso'] = gestor['nivel_acesso']
            return True, gestor['nivel_acesso']
        return False, None

    @staticmethod
    def register(data, is_diretor):
        """Handles new manager registration."""
        nome = str(data.get('nome', '')).strip()
        nome_usuario = str(data.get('nome_usuario', '')).strip().lower()
        senha = str(data.get('senha', ''))
        cargo = str(data.get('cargo', 'Cliente')).strip()
        nivel_acesso = str(data.get('nivel_acesso', 'cliente')).strip() if is_diretor else 'cliente'

        cupom = str(data.get('cupom', '')).strip().upper()

        if not nome or not nome_usuario or not senha:
            return False, "Preencha os campos obrigatórios."

        if cupom and cupom != 'CLIENTEIRO30':
            return False, "Cupom inválido ou expirado."

        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM gestores WHERE nome_usuario = %s', (nome_usuario,))
            if cur.fetchone():
                conn.close()
                return False, "Nome de usuário já cadastrado."

            senha_hash = hash_password(senha)
            plano = 'pro' if cupom == 'CLIENTEIRO30' else 'gratis'
            cur.execute(
                "INSERT INTO gestores (nome, nome_usuario, senha_hash, cargo, nivel_acesso, plano) VALUES (%s, %s, %s, %s, %s, %s)",
                (nome, nome_usuario, senha_hash, cargo, nivel_acesso, plano)
            )
        conn.commit()
        conn.close()
        return True, "Conta criada com sucesso!"

    @staticmethod
    def logout():
        session.clear()
