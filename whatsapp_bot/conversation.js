const dayjs = require('dayjs');
const utc = require('dayjs/plugin/utc');
const timezone = require('dayjs/plugin/timezone');
const { getNextAvailableSlots, formatSlotsForWhatsApp } = require('./calendar');

dayjs.extend(utc);
dayjs.extend(timezone);

// Estados Simples da Conversa
const STATES = {
    PDF_SENT: 'PDF_SENT',
    FUNNEL_START: 'FUNNEL_START',
    FUNNEL_PITCH: 'FUNNEL_PITCH',
    FUNNEL_SLOTS: 'FUNNEL_SLOTS',
    HUMAN: 'HUMAN'
};

// Sessoes em memoria
const sessions = new Map();
const SESSION_TIMEOUT = 12 * 60 * 60 * 1000; // 12h
const SLOTS_TIMEOUT = 2 * 60 * 60 * 1000; // 2h
const TZ = 'America/Sao_Paulo';

function normalizeText(value) {
    return String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toUpperCase()
        .trim();
}

function parseChoiceIntent(text) {
    const normalized = normalizeText(text);
    // Suporte a "1" ou "sim" (tem site)
    if (
        normalized === '1' ||
        normalized.includes('SIM') ||
        normalized.includes('JA TENHO') ||
        normalized.includes('TENHO SITE') ||
        normalized.includes('PROCESSO LISO')
    ) return 'SIM';
    // Suporte a "2" ou "nao" (nao tem site)
    if (
        normalized === '2' ||
        normalized.includes('NAO') ||
        normalized.includes('N TENHO') ||
        normalized.includes('N PRECISAMOS') ||
        normalized.includes('PRECISAMOS DISSO') ||
        normalized.includes('SEM SITE')
    ) return 'NAO';
    return null;
}

function getSession(phone) {
    const existing = sessions.get(phone);
    const now = Date.now();

    if (!existing || (now - Number(existing.lastActivity || 0) > SESSION_TIMEOUT)) {
        const freshSession = {
            state: STATES.FUNNEL_START,
            lastActivity: now,
            tempSlots: [],
            lastSlotsAt: 0
        };
        sessions.set(phone, freshSession);
        return freshSession;
    }

    existing.lastActivity = now;
    return existing;
}

function updateSessionState(phone, state) {
    const session = getSession(phone);
    session.state = state;
    return session;
}

function extractDateAndTime(text) {
    const dateMatch = String(text || '').match(/(\d{1,2}\/\d{1,2})/);
    const timeMatch = String(text || '').match(/(\d{1,2}:\d{2})/);
    if (!dateMatch || !timeMatch) return null;

    const [dayRaw, monthRaw] = dateMatch[1].split('/');
    const [hourRaw, minuteRaw] = timeMatch[1].split(':');

    const day = String(dayRaw).padStart(2, '0');
    const month = String(monthRaw).padStart(2, '0');
    const hour = String(hourRaw).padStart(2, '0');
    const minute = String(minuteRaw).padStart(2, '0');

    return { day, month, hour, minute };
}

function findChosenSlot(text, slots) {
    const parsed = extractDateAndTime(text);
    if (!parsed || !Array.isArray(slots) || slots.length === 0) return null;

    return slots.find((slot) => {
        const local = dayjs(slot.start).tz(TZ);
        if (!local.isValid()) return false;
        return (
            local.format('DD') === parsed.day &&
            local.format('MM') === parsed.month &&
            local.format('HH') === parsed.hour &&
            local.format('mm') === parsed.minute
        );
    }) || null;
}

async function registerAppointment(config, phone, slotStartIso) {
    const backendHost = config.backendHost || 'backend';
    const backendPort = config.backendPort || 3583;
    const internalKey = config.internalApiKey;
    if (!internalKey) {
        throw new Error('INTERNAL_API_KEY ausente no bot.');
    }

    const response = await fetch(`http://${backendHost}:${backendPort}/admin/api/register_appointment`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-API-KEY': internalKey
        },
        body: JSON.stringify({
            phone,
            date: slotStartIso
        })
    });

    const payload = await response.json().catch(() => ({}));
    return { ok: response.ok, payload };
}

async function refreshSlots(session, calendarId) {
    const slots = await getNextAvailableSlots(calendarId);
    session.tempSlots = Array.isArray(slots) ? slots : [];
    session.lastSlotsAt = Date.now();
    return session.tempSlots;
}

// Handle Msg Central
async function processMessage(phone, text, message, config = {}) {
    const session = getSession(phone);
    const calendarId = config.calendarId || 'primary';

    // Human takeover
    if (session.state === STATES.HUMAN) {
        console.log(`[BOT] Silenciado para ${phone}: atendimento humano ativo.`);
        return [];
    }

    if (session.state === STATES.PDF_SENT) {
        session.state = STATES.FUNNEL_PITCH;
    }

    // Primeira mensagem organica (sem PDF previo)
    if (session.state === STATES.FUNNEL_START) {
        session.state = STATES.FUNNEL_PITCH;

        return [
            {
                type: 'text',
                content:
                    'Ola! Sou o assistente virtual da *Clienteiro* — especialistas em trazer clientes para o seu negocio.\n\n' +
                    'Me conta uma coisa rapida:\n\n' +
                    '1️⃣ *SIM* — Ja tenho um site profissional\n' +
                    '2️⃣ *NAO* — Ainda nao tenho site\n\n' +
                    'Responda *1* ou *2*:',
                delay: 1200
            }
        ];
    }

    // Etapa de qualificacao
    if (session.state === STATES.FUNNEL_PITCH) {
        const intent = parseChoiceIntent(text);
        if (!intent) {
            return [
                {
                    type: 'text',
                    content: 'Responda *1* se ja tem site ou *2* se nao tem. Simples assim! 😊',
                    delay: 1200
                }
            ];
        }

        const slots = await refreshSlots(session, calendarId);
        if (!slots.length) {
            session.state = STATES.HUMAN;
            return [
                {
                    type: 'text',
                    content:
                        'No momento nao localizei horarios automaticos disponiveis. ' +
                        'Nosso time vai te chamar aqui para marcar o melhor horario! 🤝',
                    delay: 1200
                }
            ];
        }

        session.state = STATES.FUNNEL_SLOTS;
        const slotsMsg = formatSlotsForWhatsApp(slots);

        if (intent === 'SIM') {
            return [
                {
                    type: 'text',
                    content:
                        '✅ Otimo! Voce ja tem a base — agora e hora de escalar.\n\n' +
                        'Com nosso *WhatsApp Bot + Pacote de Leads qualificados* do seu segmento, ' +
                        'voce automatiza a captacao e multiplica seus clientes no piloto automatico.\n\n' +
                        '📅 Escolha um horario abaixo para uma demonstracao de 10 minutos:',
                    delay: 2500
                },
                { type: 'text', content: slotsMsg, delay: 1600 }
            ];
        }

        return [
            {
                type: 'text',
                content:
                    '🚀 Encontrei o gap!\n\n' +
                    'Nosso *Pacote Completo* foi feito exatamente para isso:\n\n' +
                    '✅ Site profissional de alta conversao\n' +
                    '✅ WhatsApp Bot 24h (esse aqui!)\n' +
                    '✅ Leads qualificados do seu segmento\n' +
                    '🌐 Hospedagem inclusa\n\n' +
                    'Tudo integrado, sem complicacao.\n\n' +
                    '📅 Escolha um horario para ver ao vivo em 10 minutos:',
                delay: 2800
            },
            { type: 'text', content: slotsMsg, delay: 1800 }
        ];
    }

    // Escolha de horario
    if (session.state === STATES.FUNNEL_SLOTS) {
        const slotsExpired = (Date.now() - Number(session.lastSlotsAt || 0)) > SLOTS_TIMEOUT;
        if (!Array.isArray(session.tempSlots) || session.tempSlots.length === 0 || slotsExpired) {
            await refreshSlots(session, calendarId);
        }

        const chosenSlot = findChosenSlot(text, session.tempSlots || []);
        if (!chosenSlot) {
            return [
                {
                    type: 'text',
                    content: 'Nao consegui identificar o horario. Responda no formato *DD/MM as HH:MM*, igual aos horarios enviados.',
                    delay: 1200
                }
            ];
        }

        const appt = await registerAppointment(config, phone, chosenSlot.start).catch((err) => {
            console.error('[APPT] Falha ao registrar agendamento:', err.message);
            return { ok: false, payload: {} };
        });

        const chosenLocal = dayjs(chosenSlot.start).tz(TZ);
        const dateLabel = chosenLocal.format('DD/MM');
        const timeLabel = chosenLocal.format('HH:mm');
        const dayKey = chosenLocal.format('YYYY-MM-DD');
        session.state = STATES.HUMAN;

        if (!appt.ok) {
            return [
                {
                    type: 'text',
                    content: `Recebi sua preferencia para *${dateLabel} as ${timeLabel}h*. Tive uma instabilidade ao salvar, nosso time vai confirmar com voce em breve! 🤝`,
                    delay: 1500
                }
            ];
        }

        const alreadyScheduledToday = Boolean(appt.payload && appt.payload.already_scheduled_today);
        const confirmationText = alreadyScheduledToday
            ? `Seu contato para *${dateLabel} as ${timeLabel}h* ja esta registrado. Nosso estrategista confirma por aqui em instantes! 🎯`
            : `✅ Confirmado!\n\nDemonstração agendada para *${dateLabel} as ${timeLabel}h*.\n\nNosso estrategista vai entrar em contato com o link. Ate la! 🚀`;

        return [
            { type: 'reaction', emoji: '✅' },
            {
                type: 'text',
                content: confirmationText,
                delay: 1800
            }
        ];
    }

    return [];
}

module.exports = {
    processMessage,
    updateSessionState,
    STATES,
    getSession
};
