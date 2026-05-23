const express = require('express');
const axios = require('axios');

const app = express();
app.use(express.json());

const PORT = Number(process.env.PORT || 3000);
const EVOLUTION_BASE_URL = String(process.env.EVOLUTION_BASE_URL || '').replace(/\/+$/, '');
const EVOLUTION_INSTANCE = process.env.EVOLUTION_INSTANCE || '';
const EVOLUTION_API_KEY = process.env.EVOLUTION_API_KEY || '';
const PRIZE_PDF_URL = process.env.PRIZE_PDF_URL || 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf';

function evolutionHeaders() {
  return {
    apikey: EVOLUTION_API_KEY,
    'Content-Type': 'application/json',
  };
}

function sanitizePhone(phone) {
  return String(phone || '').replace(/\D/g, '');
}

function validateConfig() {
  const missing = [];
  if (!EVOLUTION_API_KEY) missing.push('EVOLUTION_API_KEY');
  if (!EVOLUTION_INSTANCE) missing.push('EVOLUTION_INSTANCE');
  if (!EVOLUTION_BASE_URL) missing.push('EVOLUTION_BASE_URL');
  return missing;
}

async function sendTextMessage(phone, text) {
  const number = sanitizePhone(phone);
  const endpoint = `${EVOLUTION_BASE_URL}/message/sendText/${EVOLUTION_INSTANCE}`;

  return axios.post(
    endpoint,
    {
      number,
      text,
      options: {
        delay: 1200,
        presence: 'composing',
      },
    },
    { headers: evolutionHeaders(), timeout: 15000 }
  );
}

async function sendPrizePdf(phone) {
  const number = sanitizePhone(phone);
  const endpoint = `${EVOLUTION_BASE_URL}/message/sendMedia/${EVOLUTION_INSTANCE}`;

  return axios.post(
    endpoint,
    {
      number,
      mediatype: 'document',
      media: PRIZE_PDF_URL,
      fileName: 'premio-checkleads.pdf',
      caption: 'Conforme prometido, aqui esta o seu premio. Qualquer duvida, e so me chamar!',
    },
    { headers: evolutionHeaders(), timeout: 20000 }
  );
}

app.get('/health', (req, res) => {
  const missing = validateConfig();
  res.status(missing.length ? 503 : 200).json({
    ok: missing.length === 0,
    service: 'roulette-webhook',
    missing,
  });
});

async function handleWebhook(req, res) {
  const missing = validateConfig();
  if (missing.length) {
    return res.status(500).json({
      ok: false,
      error: 'Configuracao incompleta do servico.',
      missing,
    });
  }

  const payload = req.body || {};
  const event = payload.event;

  try {
    if (event === 'lead_captured') {
      const name = payload.name || 'Cliente';
      const phone = payload.phone;
      if (!phone) {
        return res.status(400).json({ ok: false, error: 'Campo "phone" e obrigatorio em lead_captured.' });
      }

      const message = `Ola ${name}! 🚀 Vi que voce se cadastrou para girar a roleta do CheckLeads Elite. Estou na torcida aqui, boa sorte no seu giro!`;
      const result = await sendTextMessage(phone, message);
      return res.status(200).json({ ok: true, event, action: 'lead_welcome_sent', evolution: result.data });
    }

    if (event === 'prize_won') {
      const prize = payload.prize || 'Premio';
      const lead = payload.lead || {};
      const name = lead.name || 'Cliente';
      const phone = lead.phone;
      if (!phone) {
        return res.status(400).json({ ok: false, error: 'Campo "lead.phone" e obrigatorio em prize_won.' });
      }

      const congrats = `Parabens, ${name}! 🎉 Voce acabou de ganhar: *${prize}*.`;
      const textResult = await sendTextMessage(phone, congrats);
      const mediaResult = await sendPrizePdf(phone);

      return res.status(200).json({
        ok: true,
        event,
        action: 'prize_text_and_pdf_sent',
        evolutionTextResponse: textResult.data,
        evolutionMediaResponse: mediaResult.data,
      });
    }

    return res.status(400).json({
      ok: false,
      error: 'Evento nao suportado. Use "lead_captured" ou "prize_won".',
      receivedEvent: event || null,
    });
  } catch (error) {
    const details = error.response?.data || error.message;
    console.error('[roulette-webhook] Erro ao processar webhook:', details);
    return res.status(500).json({
      ok: false,
      error: 'Falha ao processar webhook.',
      details,
    });
  }
}

app.post('/webhook', handleWebhook);
app.post('/webhook/roleta', handleWebhook);

app.listen(PORT, () => {
  console.log(`[roulette-webhook] Listening on port ${PORT}`);
  console.log(`[roulette-webhook] Evolution base: ${EVOLUTION_BASE_URL}`);
  console.log(`[roulette-webhook] Evolution instance: ${EVOLUTION_INSTANCE}`);
});
