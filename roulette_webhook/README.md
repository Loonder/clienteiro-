# Roulette Webhook (Evolution API)

Servico Node.js para receber webhooks da roleta e disparar WhatsApp via Evolution API.

## Eventos aceitos

- `lead_captured`
- `prize_won`

## Variaveis de ambiente

- `PORT` (default `3000`)
- `EVOLUTION_BASE_URL` (ex: `https://evolution.seudominio.com.br`)
- `EVOLUTION_INSTANCE` (id/nome da instancia conectada)
- `EVOLUTION_API_KEY` (apikey da Evolution)
- `PRIZE_PDF_URL` (URL publica do PDF premio)

## Subir com Docker Compose

No diretorio `checkleads`:

```bash
docker compose up -d roulette-webhook
```

## Endpoint do frontend da roleta

Use no `roulette/script.js`:

```js
const WEBHOOK_URL = "https://seudominio.com.br/webhook/roleta";
```

## Teste rapido

```bash
curl -X POST http://127.0.0.1:3000/webhook/roleta \
  -H "Content-Type: application/json" \
  -d '{"event":"lead_captured","name":"Teste","phone":"5511999999999","timestamp":"2026-04-22T10:00:00.000Z"}'
```
