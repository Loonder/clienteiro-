# Clienteiro

Plataforma de prospeccao, qualificacao e atendimento automatizado para transformar leads brutos em oportunidades comerciais acompanhaveis.

O projeto combina uma aplicacao Flask, um painel administrativo, fluxo LGPD, geracao de relatorios, roleta/kiosk para eventos e um bot de WhatsApp em Node.js. A proposta e simples: captar, qualificar, priorizar e acompanhar contatos com rastreabilidade operacional.

## Visao Geral

Clienteiro foi desenhado para demonstrar uma operacao comercial ponta a ponta:

- Captura e organizacao de leads por nicho, cidade e origem.
- Scoring para priorizar oportunidades com maior chance de conversao.
- Painel admin para acompanhar leads, eventos, configuracoes e auditoria.
- Kiosk/roleta para ativacoes presenciais e feiras.
- Bot de WhatsApp para continuidade do atendimento e agendamento.
- Trilhas de LGPD com consentimento, retencao, exclusao e auditoria.
- Deploy conteinerizado com Docker e Docker Compose.

## Stack

- Backend: Python, Flask, Flask-WTF, Flask-Limiter, Flask-Talisman.
- Banco: PostgreSQL/Supabase em producao; SQLite apenas para desenvolvimento legado/local.
- Bot: Node.js, Express, whatsapp-web.js e provider Evolution opcional.
- Frontend: HTML, CSS e JavaScript sem framework.
- Qualidade: pytest, Bandit e Safety.
- Deploy: Docker, Docker Compose e Gunicorn.

## Estrutura

```text
.
|-- app.py                         # Aplicacao Flask principal
|-- core/                          # Processamento, scoring, DB, auth e relatorios
|-- services/                      # Casos de uso de auth, leads e LGPD
|-- templates/                     # Telas web
|-- static/                        # CSS, imagens e manifest
|-- tests/                         # Testes automatizados Python
|-- whatsapp_bot/                  # Bot de WhatsApp
|-- roulette/                      # Frontend da roleta
|-- roulette_webhook/              # Webhook Node.js da roleta
|-- production_assets/             # Artes de producao
|-- docker-compose.yml             # Stack principal
|-- Dockerfile                     # Imagem da aplicacao Flask
|-- .env.example                   # Modelo seguro de variaveis
```

## Seguranca

O repositorio foi preparado para ser publicado sem segredos reais. Arquivos como `.env`, bancos locais, QR codes, sessoes do WhatsApp, chaves privadas e arquivos de credenciais sao ignorados pelo Git.

Antes de publicar ou apresentar:

1. Confirme que `git status --short` nao mostra `.env`, `.db`, QR code, sessao ou credencial.
2. Gere valores fortes para `SECRET_KEY`, `INTERNAL_API_KEY`, senhas iniciais e tokens externos.
3. Rotacione qualquer token que ja tenha sido usado em arquivo versionado no passado.
4. Nunca rode producao com os placeholders `CHANGE_ME_*`.
5. Use HTTPS e proxy reverso com headers preservando `X-Forwarded-*`.

Gerar chaves locais:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Variaveis de Ambiente

Crie os arquivos locais a partir dos modelos:

```bash
cp .env.example .env
cp whatsapp_bot/.env.example whatsapp_bot/.env
```

Variaveis obrigatorias em producao:

- `SECRET_KEY`: chave de sessao Flask.
- `INTERNAL_API_KEY`: chave compartilhada entre backend e bot.
- `SUPABASE_DB_URL` ou `DATABASE_URL`: conexao PostgreSQL.
- `DEFAULT_ADMIN_PASS`: senha temporaria do primeiro diretor, removida/trocada apos o primeiro boot.
- `EVOLUTION_API_KEY`: apenas se a integracao Evolution estiver habilitada.
- `GEMINI_API_KEY`: apenas se os recursos de IA do bot estiverem habilitados.

## Como Rodar com Docker

```bash
docker compose up -d --build
```

Servicos principais:

- Aplicacao web: `http://localhost:3580`
- Backend Flask no container: porta interna `3583`
- Bot WhatsApp: porta interna `3582`
- Webhook da roleta: porta interna `3000`

## Como Rodar Localmente

Backend:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Bot:

```bash
cd whatsapp_bot
npm install
npm start
```

Webhook da roleta:

```bash
cd roulette_webhook
npm install
npm start
```

## Testes e Auditoria

Testes Python:

```bash
pytest -q
```

Auditoria estatica Python:

```bash
bandit -r . -x .venv,tests,__pycache__
```

Dependencias Python:

```bash
safety check -r requirements.txt
```

Busca local por possiveis segredos:

```bash
rg -n --hidden -S "(SECRET|PASSWORD|TOKEN|API_KEY|PRIVATE KEY|DATABASE_URL)" -g "!.git" -g "!.venv" -g "!__pycache__"
```

## LGPD

O projeto inclui camadas para operar com responsabilidade:

- Registro de consentimento e versao do termo.
- Base legal configuravel.
- Retencao de leads por janela definida.
- Fluxos de exclusao e auditoria.
- Documentos de apoio em `LGPD_READINESS.md`, `templates/privacy.html` e `templates/terms.html`.

## Fluxo de Producao

Checklist recomendado:

1. Preencher `.env` com valores reais e fortes.
2. Rodar migracoes/inicializacao necessarias.
3. Subir a stack com Docker Compose.
4. Acessar o painel admin e trocar credenciais temporarias.
5. Validar captura, dashboard, LGPD, roleta e bot.
6. Rodar `pytest`, `bandit` e auditoria de segredos antes de publicar.

## Observacoes para a Banca

Clienteiro nao e apenas uma landing page. Ele entrega um ciclo operacional completo:

- Entrada do lead.
- Qualificacao e scoring.
- Visualizacao gerencial.
- Acionamento por WhatsApp.
- Controle de consentimento.
- Auditoria de eventos.
- Deploy conteinerizado.

Isso permite avaliar arquitetura, seguranca, produto, operacao e aderencia a LGPD em um mesmo projeto.

## Licenca

Projeto academico/demonstrativo. Ajuste a licenca conforme a politica do grupo antes de publicacao definitiva.
