# Clienteiro

Clienteiro e uma plataforma Python para prospeccao, qualificacao e atendimento automatizado de leads. O projeto demonstra um fluxo comercial completo: captura do contato, scoring, painel administrativo, auditoria, LGPD, roleta/kiosk para eventos e continuidade via WhatsApp.

O foco do projeto e mostrar como uma aplicacao backend em Python pode organizar uma operacao real de vendas, com regras de negocio, seguranca, persistencia, testes e deploy conteinerizado.

## Principais Recursos

- Captura e organizacao de leads por nicho, cidade e origem.
- Scoring para priorizar contatos com maior potencial comercial.
- Painel administrativo com acompanhamento de leads e indicadores.
- Kiosk/roleta para ativacoes presenciais.
- Fluxo LGPD com consentimento, retencao e solicitacoes do titular.
- Bot de WhatsApp em Node.js para apoio ao atendimento.
- Webhook da roleta integrado a provider externo de WhatsApp.
- Docker Compose para execucao da stack.
- Testes automatizados e auditoria de seguranca.

## Como Python Foi Usado

Python e o nucleo do projeto. Ele foi usado para construir a aplicacao principal com Flask e para concentrar as regras de negocio.

- `app.py`: inicializa a aplicacao Flask, rotas web, APIs, seguranca, CSRF, rate limit e integracoes.
- `core/`: contem processamento, scoring, conexao com banco, autenticacao, scraping e geracao de relatorios.
- `services/`: organiza casos de uso como autenticacao, leads e LGPD.
- `tests/`: valida regras de negocio, autenticacao, fallback de processamento e endpoints.
- `requirements.txt`: fixa as dependencias Python usadas em producao e nos testes.

Bibliotecas Python relevantes:

- Flask para backend web.
- Flask-WTF para CSRF e formularios.
- Flask-Limiter para rate limiting.
- Flask-Talisman para headers de seguranca.
- psycopg2 para PostgreSQL/Supabase.
- fpdf2 e qrcode para relatorios e artefatos.
- pytest para testes.
- Bandit e Safety para auditoria de seguranca.

## Stack

- Backend principal: Python 3.11, Flask e Gunicorn.
- Banco de dados: PostgreSQL/Supabase em producao.
- Frontend: HTML, CSS e JavaScript.
- Bot: Node.js, Express e whatsapp-web.js/Evolution provider.
- Deploy: Docker e Docker Compose.
- Qualidade: pytest, Bandit, Safety e npm audit.

## Estrutura

```text
.
|-- app.py                         # Aplicacao Flask principal
|-- core/                          # Regras centrais, scoring, DB, auth e relatorios
|-- services/                      # Casos de uso de leads, auth e LGPD
|-- templates/                     # Telas HTML
|-- static/                        # CSS, imagens e manifest
|-- tests/                         # Testes automatizados Python
|-- whatsapp_bot/                  # Bot de WhatsApp em Node.js
|-- roulette/                      # Frontend da roleta
|-- roulette_webhook/              # Webhook Node.js da roleta
|-- docker-compose.yml             # Stack principal
|-- Dockerfile                     # Imagem da aplicacao Python
|-- .env.example                   # Modelo seguro de configuracao
```

## Seguranca

Este repositorio foi preparado para publicacao academica sem segredos reais. Arquivos de ambiente, bancos locais, sessoes de WhatsApp, QR codes, chaves privadas e tokens estao bloqueados por `.gitignore` e `.dockerignore`.

Regras adotadas:

- `.env` real nunca deve ser versionado.
- `.env.example` contem somente placeholders.
- `SECRET_KEY` e `INTERNAL_API_KEY` devem ser gerados com valores fortes.
- Credenciais temporarias devem ser trocadas apos o primeiro acesso.
- Dependencias foram auditadas com Safety e npm audit.
- Codigo Python foi checado com Bandit para achados de alta severidade.

Gerar chaves fortes:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Variaveis de Ambiente

Crie os arquivos locais a partir dos exemplos:

```bash
cp .env.example .env
cp whatsapp_bot/.env.example whatsapp_bot/.env
```

Variaveis principais:

- `SECRET_KEY`: chave de sessao Flask.
- `INTERNAL_API_KEY`: chave compartilhada entre backend e bot.
- `SUPABASE_DB_URL` ou `DATABASE_URL`: conexao PostgreSQL.
- `DEFAULT_ADMIN_PASS`: senha temporaria do primeiro diretor.
- `EVOLUTION_API_KEY`: usada se a integracao Evolution estiver ativa.
- `GEMINI_API_KEY`: usada se recursos de IA do bot estiverem ativos.

## Como Rodar com Docker

```bash
docker compose up -d --build
```

Servicos:

- Aplicacao web: `http://localhost:3580`
- Backend Flask: porta interna `3583`
- Bot WhatsApp: porta interna `3582`
- Webhook da roleta: porta interna `3000`

## Como Rodar Localmente

Backend Python:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Bot WhatsApp:

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

Auditoria Python:

```bash
bandit -r app.py core services -x tests -q --severity-level high
safety check -r requirements.txt
```

Auditoria Node:

```bash
npm --prefix whatsapp_bot audit --audit-level=high --omit=dev
npm --prefix roulette_webhook audit --audit-level=high --omit=dev
```

Varredura simples de segredos:

```bash
rg -n --hidden -S "(SECRET|PASSWORD|TOKEN|API_KEY|PRIVATE KEY|DATABASE_URL|postgresql://)" -g "!.git" -g "!.venv" -g "!node_modules"
```

## Resultado de Validacao

Na preparacao desta versao publica:

- `pytest -q`: 44 testes passaram.
- `safety check -r requirements.txt`: nenhuma vulnerabilidade conhecida reportada.
- `bandit --severity-level high`: nenhum achado de alta severidade.
- `npm audit` no bot e webhook: nenhuma vulnerabilidade alta reportada.
- Varredura de segredos conhecidos: sem achados.

## Observacao Para Avaliacao

Clienteiro nao e apenas uma interface. O projeto demonstra backend Python, organizacao em servicos, persistencia, seguranca, testes, integracao com Node.js, deploy em Docker e preocupacao com LGPD. A arquitetura foi pensada para representar um produto funcional e apresentavel em ambiente academico.

## Licenca

Projeto academico/demonstrativo.
