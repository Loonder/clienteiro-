import os
import uuid
from datetime import datetime, timedelta

from core.db_manager import get_db_connection


class LGPDService:
    REQUEST_TYPES = {
        "confirmacao",
        "acesso",
        "correcao",
        "anonimizacao",
        "eliminacao",
        "portabilidade",
        "revogacao_consentimento",
    }

    STATUS_TYPES = {"recebido", "em_analise", "concluido", "negado"}

    @staticmethod
    def _clean(value, fallback="", max_len=220):
        text = str(value or "").strip()
        text = " ".join(text.split())
        return text[:max_len] if text else fallback

    @staticmethod
    def _build_protocol():
        stamp = datetime.utcnow().strftime("%Y%m%d")
        token = uuid.uuid4().hex[:8].upper()
        return f"LGPD-{stamp}-{token}"

    @staticmethod
    def create_request(payload, ip):
        req_type = LGPDService._clean(payload.get("request_type"), "", 40).lower()
        if req_type not in LGPDService.REQUEST_TYPES:
            return {"ok": False, "error": "Tipo de solicitacao LGPD invalido."}

        requester_name = LGPDService._clean(payload.get("requester_name"), "", 100)
        requester_phone = LGPDService._clean(payload.get("requester_phone"), "", 30)
        requester_email = LGPDService._clean(payload.get("requester_email"), "", 120).lower()
        message = LGPDService._clean(payload.get("message"), "", 1000)

        if not requester_name:
            return {"ok": False, "error": "Informe o nome do titular."}
        if not requester_phone and not requester_email:
            return {"ok": False, "error": "Informe telefone ou email para retorno."}

        protocol = LGPDService._build_protocol()

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lgpd_requests
                        (protocol, requester_name, requester_phone, requester_email, request_type, message, ip)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        protocol,
                        requester_name,
                        requester_phone,
                        requester_email,
                        req_type,
                        message,
                        LGPDService._clean(ip, "unknown", 80),
                    ),
                )
            conn.commit()
            return {"ok": True, "protocol": protocol}
        finally:
            conn.close()

    @staticmethod
    def list_requests(limit=200):
        safe_limit = max(1, min(int(limit or 200), 500))
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, protocol, requester_name, requester_phone, requester_email,
                           request_type, message, status, created_at, handled_at, handled_by
                    FROM lgpd_requests
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (safe_limit,),
                )
                rows = cur.fetchall()
            return {"ok": True, "requests": [dict(r) for r in rows]}
        finally:
            conn.close()

    @staticmethod
    def update_request_status(request_id, status, handled_by):
        new_status = LGPDService._clean(status, "", 40).lower()
        if new_status not in LGPDService.STATUS_TYPES:
            return {"ok": False, "error": "Status invalido."}

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE lgpd_requests
                    SET status=%s, handled_at=CURRENT_TIMESTAMP, handled_by=%s
                    WHERE id=%s
                    RETURNING id
                    """,
                    (new_status, handled_by, request_id),
                )
                row = cur.fetchone()
            conn.commit()
            if not row:
                return {"ok": False, "error": "Solicitacao nao encontrada."}
            return {"ok": True}
        finally:
            conn.close()

    @staticmethod
    def retention_days():
        try:
            days = int(os.getenv("LEAD_RETENTION_DAYS", "180"))
            return max(30, min(days, 1825))
        except Exception:
            return 180

    @staticmethod
    def compute_retention_until():
        return (datetime.utcnow() + timedelta(days=LGPDService.retention_days())).date()

    @staticmethod
    def run_retention_cleanup():
        conn = get_db_connection()
        try:
            days = LGPDService.retention_days()
            with conn.cursor() as cur:
                # Backfill para registros legados sem data de retencao
                cur.execute(
                    """
                    UPDATE internal_leads
                    SET retention_until = DATE(timestamp + (%s * INTERVAL '1 day'))
                    WHERE retention_until IS NULL
                    """,
                    (days,),
                )

                cur.execute(
                    """
                    UPDATE internal_leads
                    SET user_name='ANONYMIZED',
                        company_name='ANONYMIZED',
                        city='ANONYMIZED',
                        nicho='ANONYMIZED',
                        phone=NULL,
                        pdf_path=NULL,
                        consent=0,
                        anonymized=1
                    WHERE anonymized=0
                      AND retention_until IS NOT NULL
                      AND retention_until <= CURRENT_DATE
                    RETURNING id
                    """
                )
                rows = cur.fetchall()
            conn.commit()
            return {"ok": True, "anonymized_count": len(rows)}
        finally:
            conn.close()
