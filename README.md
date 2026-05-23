# Clienteiro

Clienteiro e uma plataforma Python para prospeccao, qualificacao e acompanhamento de leads. O projeto demonstra um fluxo comercial completo: captura do contato, scoring, painel administrativo, LGPD, roleta/kiosk para eventos e apoio de atendimento via WhatsApp.

## Objetivo

O objetivo do projeto e mostrar como Python pode ser usado para construir uma aplicacao web funcional, com backend, regras de negocio, persistencia, testes e deploy em Docker.

## Como Python Foi Usado

Python e o nucleo do Clienteiro.

- `app.py`: aplicacao Flask principal, rotas web, APIs, configuracoes e integracoes.
- `core/`: regras centrais de processamento, scoring, banco de dados, autenticacao e relatorios.
- `services/`: camada de servicos para autenticacao, leads e LGPD.
- `tests/`: testes automatizados das principais regras e endpoints.
- `requirements.txt`: dependencias Python fixadas para reproducibilidade.

Principais bibliotecas:

- Flask para o backend web.
- psycopg2 para PostgreSQL/Supabase.
- Flask-WTF, Flask-Limiter e Flask-Talisman para seguranca da aplicacao.
- fpdf2 e qrcode para relatorios e artefatos.
- pytest para testes automatizados.

## Funcionalidades

- Cadastro e organizacao de leads.
- Scoring para priorizacao comercial.
- Painel administrativo.
- Fluxos basicos de LGPD.
- Kiosk/roleta para captacao em eventos.
- Bot de WhatsApp em Node.js.
- Webhook da roleta.
- Execucao com Docker Compose.

## Stack

- Python 3.11
- Flask
- PostgreSQL/Supabase
- HTML, CSS e JavaScript
- Node.js para o bot e webhook
- Docker e Docker Compose
- pytest

## Estrutura

```text
.
|-- app.py                 # Aplicacao Flask principal
|-- core/                  # Regras centrais do sistema
|-- services/              # Servicos de dominio
|-- templates/             # Paginas HTML
|-- static/                # CSS, imagens e arquivos estaticos
|-- tests/                 # Testes automatizados
|-- whatsapp_bot/          # Bot de WhatsApp
|-- roulette/              # Interface da roleta
|-- roulette_webhook/      # Webhook da roleta
|-- Dockerfile             # Imagem da aplicacao Python
|-- docker-compose.yml     # Orquestracao local
|-- .env.example           # Modelo de configuracao
```

## Configuracao

Copie os arquivos de exemplo e preencha as variaveis locais:

```bash
cp .env.example .env
cp whatsapp_bot/.env.example whatsapp_bot/.env
```

Variaveis importantes:

- `SECRET_KEY`
- `INTERNAL_API_KEY`
- `SUPABASE_DB_URL` ou `DATABASE_URL`
- `DEFAULT_ADMIN_PASS`
- `EVOLUTION_API_KEY`, se a integracao Evolution for usada
- `GEMINI_API_KEY`, se os recursos de IA do bot forem usados

Os arquivos `.env` reais nao fazem parte do repositorio.

## Como Rodar

Com Docker:

```bash
docker compose up -d --build
```

Localmente:

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

Webhook:

```bash
cd roulette_webhook
npm install
npm start
```

## Testes

```bash
pytest -q
```

Na versao enviada para avaliacao, a suite automatizada passa com 44 testes.

## Observacao

Este e um projeto academico/demonstrativo. A proposta e apresentar uma solucao de produto com backend Python, organizacao de codigo, integracoes, testes e cuidado com configuracao por ambiente.
