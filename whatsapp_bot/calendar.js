const { google } = require('googleapis');
const dayjs = require('dayjs');
const utc = require('dayjs/plugin/utc');
const timezone = require('dayjs/plugin/timezone');

dayjs.extend(utc);
dayjs.extend(timezone);

let calendar = null;
const ENABLE_MOCK_CALENDAR = String(process.env.ENABLE_MOCK_CALENDAR || '')
    .trim()
    .toLowerCase() === 'true';

async function initCalendar() {
    try {
        const clientEmail = process.env.GCLOUD_EMAIL;
        const privateKey = process.env.GCLOUD_PRIVATE_KEY
            ? process.env.GCLOUD_PRIVATE_KEY.replace(/\\n/g, '\n')
            : null;

        if (!clientEmail || !privateKey) {
            console.warn('[CAL] Google credentials not fully configured. Calendar integration will stay disabled.');
            return false;
        }

        const auth = new google.auth.GoogleAuth({
            credentials: {
                client_email: clientEmail,
                private_key: privateKey,
            },
            scopes: ['https://www.googleapis.com/auth/calendar.readonly'],
        });

        const authClient = await auth.getClient();
        calendar = google.calendar({ version: 'v3', auth: authClient });
        console.log('[CAL] Google Calendar connected successfully');
        return true;
    } catch (err) {
        console.error('[CAL] Error connecting Google Calendar', err.message);
        return false;
    }
}

function getMockSlots() {
    return [
        { id: 'mock1', start: dayjs().add(1, 'day').hour(10).minute(0).toISOString() },
        { id: 'mock2', start: dayjs().add(1, 'day').hour(14).minute(30).toISOString() },
        { id: 'mock3', start: dayjs().add(2, 'day').hour(11).minute(0).toISOString() },
    ];
}

async function getNextAvailableSlots(calendarId = 'primary', daysAhead = 14) {
    if (!calendar) {
        return ENABLE_MOCK_CALENDAR ? getMockSlots() : [];
    }

    try {
        const now = dayjs();
        const end = now.add(daysAhead, 'day');

        const response = await calendar.events.list({
            calendarId,
            timeMin: now.toISOString(),
            timeMax: end.toISOString(),
            singleEvents: true,
            orderBy: 'startTime',
            q: 'Disponivel',
        });

        const slots = (response.data.items || [])
            .filter((event) => {
                const title = String(event.summary || '').toLowerCase();
                return title.includes('disponivel');
            })
            .map((event) => ({
                id: event.id,
                start: event.start.dateTime || event.start.date,
                end: event.end.dateTime || event.end.date,
            }))
            .slice(0, 3);

        if (slots.length === 0) {
            return ENABLE_MOCK_CALENDAR ? getMockSlots() : [];
        }

        return slots;
    } catch (err) {
        console.error('[CAL] Error fetching slots', err.message);
        return [];
    }
}

function formatSlotsForWhatsApp(slots) {
    if (!slots || slots.length === 0) {
        return 'No momento, nao encontrei horarios disponiveis na agenda automatica. Nosso time vai te chamar aqui para encontrar o melhor encaixe.';
    }

    let result = '*Proximos horarios disponiveis:*\n\n';

    slots.forEach((slot) => {
        const date = dayjs(slot.start).tz('America/Sao_Paulo');
        const dateStr = date.format('DD/MM (dddd)');
        const time = date.format('HH:mm');
        result += `- ${dateStr} as ${time}h\n`;
    });

    result += '\nQual desses fica melhor para voce?';
    return result;
}

module.exports = {
    initCalendar,
    getNextAvailableSlots,
    formatSlotsForWhatsApp,
};
