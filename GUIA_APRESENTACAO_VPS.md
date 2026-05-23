# Guia de Apresentacao VPS

## Objetivo

Rodar o Clienteiro em modo seguro no dia a dia e ativar modo evento apenas quando necessario.

## Pre-requisitos

- Docker e Docker Compose instalados na VPS
- Arquivo `.env` em `checkleads/.env`

## Modo Diario (baixo consumo)

Executa apenas backend.

```bash
cd /caminho/checkleads_elite/checkleads
docker compose up -d --build backend
```

## Modo Apresentacao (evento)

Ativa backend + bot + colheita.

```bash
cd /caminho/checkleads_elite/checkleads
docker compose --profile bot --profile harvest up -d --build
```

## Parar colheita apos evento

```bash
cd /caminho/checkleads_elite/checkleads
docker compose stop harvester
docker compose rm -f harvester
```

## Voltar ao modo diario

```bash
cd /caminho/checkleads_elite/checkleads
docker compose --profile bot --profile harvest down
docker compose up -d backend
```

## Validacao rapida

```bash
docker compose ps
docker compose logs --tail=80 backend
docker compose logs --tail=80 bot
docker compose logs --tail=80 harvester
```

## Endpoints

- App: `http://SEU_IP:3583`
- Admin: `http://SEU_IP:3583/admin`
- Live: `http://SEU_IP:3583/live`
- Bot status (interno): `http://SEU_IP:3582/status`

## Flags criticas (.env)

- `LEADS_SOURCE=db`
- `ENABLE_LIVE_SCRAPING=false`
- `ENABLE_STREAM_HARVEST=false`
- `ENABLE_HARVEST=false`
- `ENABLE_BOT=false` (arquivo do bot)

Use `true` apenas no modo evento.
