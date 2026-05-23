# LGPD Readiness - Clienteiro

## Escopo

Este documento resume controles de privacidade implementados no produto e pontos de governanca para apresentacao executiva.

Nao constitui parecer juridico.

## Controles implementados

1. Consentimento explicito no formulario principal antes do envio.
2. Registro de evidencia de consentimento no banco:
   - `consent=1`
   - `consent_at`
   - `consent_ip`
   - `consent_version`
   - `legal_basis`
3. Canal de direitos do titular:
   - Pagina: `/lgpd`
   - API: `POST /api/lgpd/request`
   - Protocolo unico para rastreabilidade.
4. Backoffice para tratativa LGPD:
   - `GET /admin/api/lgpd/requests`
   - `POST /admin/api/lgpd/requests/<id>/status`
5. Retencao e anonimizacao operacional:
   - `POST /admin/api/lgpd/run_retention`
   - anonimizacao automatica para registros com `retention_until` vencido.
6. Auditoria:
   - Acoes administrativas registradas em `audit_log`.

## Mapeamento rapido para LGPD (operacional)

- Art. 6 (principios): minimizacao, necessidade, transparencia e responsabilizacao por trilha de auditoria e retencao.
- Art. 7 e 8 (base legal/consentimento): consentimento explicito e rastreavel.
- Art. 9 (informacoes ao titular): aviso de privacidade e canal dedicado.
- Art. 18 (direitos do titular): canal e fluxo de atendimento/protocolo.
- Art. 46 (seguranca): controles tecnicos e administrativos no tratamento.
- Art. 48 (incidentes): processo interno deve prever comunicacao a ANPD e titulares quando houver risco/dano relevante.

## Operacao recomendada

1. Definir `DPO_EMAIL` em producao.
2. Definir `LEAD_RETENTION_DAYS` conforme orientacao juridica.
3. Rodar rotina de retencao periodicamente (manual ou agendada).
4. Tratar solicitacoes LGPD com SLA documentado.
5. Manter evidencias de resposta aos titulares.

## Lacunas que ainda valem evolucao

1. Painel visual LGPD no admin (cards de SLA e fila de solicitacoes).
2. Relatorio de Impacto a Protecao de Dados (RIPD) para casos de maior risco.
3. Playbook de incidente com matriz de severidade e responsabilidades.
4. DPA/contratos com operadores e fornecedores externos.
