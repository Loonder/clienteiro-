# Roteiro Para Apresentacao

## Abertura

Clienteiro e uma plataforma de prospeccao e atendimento automatizado. O objetivo e transformar captura de leads em uma operacao rastreavel: coleta, scoring, painel admin, LGPD, kiosk/roleta e continuidade via WhatsApp.

## O Que Mostrar Primeiro

1. `README.md`: visao geral, stack e como rodar.
2. `app.py` + `services/`: arquitetura Flask e casos de uso.
3. `templates/` e `static/`: interface web.
4. `whatsapp_bot/`: automacao de atendimento.
5. `tests/`: cobertura automatizada.
6. `SECURITY.md` e `RELATORIO_FORENSE.md`: maturidade de seguranca.

## Demo Recomendada

1. Abrir landing/kiosk.
2. Capturar um lead.
3. Mostrar o lead no painel admin.
4. Mostrar logs/auditoria.
5. Mostrar fluxo LGPD.
6. Mostrar configuracao segura por `.env.example`.
7. Mostrar testes passando.

## Comandos Para Rodar Antes da Banca

```bash
pytest -q
bandit -r app.py core services test_db.py -x tests -q --severity-level high
safety check -r requirements.txt
npm --prefix whatsapp_bot audit --audit-level=high --omit=dev
npm --prefix roulette_webhook audit --audit-level=high --omit=dev
docker compose config --quiet
```

## Respostas Prontas

### "Tem senha no GitHub?"

"No codigo atual, nao. A auditoria encontrou credenciais no historico antigo, tratadas como incidente. A remediacao foi remover do indice, sanitizar exemplos, reforcar `.gitignore`/`.dockerignore`, rotacionar credenciais e publicar a versao final com historico limpo."

### "Como voces lidam com LGPD?"

"O sistema tem termos, politica de privacidade, registro de solicitacoes LGPD, auditoria de acoes e configuracao de retencao. A base legal e parametrizada por ambiente."

### "O projeto e so tela bonita?"

"Nao. Existe backend Flask, banco PostgreSQL/Supabase, servicos, testes, bot Node.js, webhook, relatorios, Docker e controles de seguranca."

### "Como sabem que esta seguro?"

"Nao prometemos seguranca absoluta. Demonstramos processo: varredura de segredos, remocao de defaults inseguros, auditoria de dependencias, Bandit, Safety, npm audit, testes automatizados e politica de resposta a incidente."

## Ordem dos Slides

1. Problema: perda de leads e follow-up manual.
2. Solucao: Clienteiro como pipeline comercial.
3. Arquitetura: Flask, PostgreSQL, Node bot, webhook.
4. Funcionalidades: scoring, admin, kiosk, WhatsApp, LGPD.
5. Seguranca: `.env`, rotacao, auditoria, CI.
6. Demo.
7. Resultados de validacao.
8. Aprendizados e proximos passos.

## Frase Final

"O diferencial do projeto nao e so automatizar captura de lead; e mostrar uma operacao comercial com produto, engenharia, compliance e resposta madura a riscos reais."
