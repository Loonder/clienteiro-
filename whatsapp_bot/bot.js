const express = require('express');
const WhatsAppEngine = require('./engine/WhatsAppEngine');
const { MessageMedia } = require('whatsapp-web.js'); // Keep for media handling in WWebJS mode
const fs = require('fs');
const path = require('path');
const dotenv = require('dotenv');
const { processMessage, updateSessionState, STATES } = require('./conversation');
const { initCalendar } = require('./calendar');

dotenv.config();

const app = express();
app.use(express.json());
app.use((req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-API-KEY');
    res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
    if (req.method === 'OPTIONS') return res.sendStatus(204);
    next();
});

const PORT = process.env.PORT || 3582;
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY;
if (!INTERNAL_API_KEY) {
    console.error('[SECURITY] INTERNAL_API_KEY ausente. Configure a mesma chave do backend antes de iniciar o bot.');
    process.exit(1);
}
const envBool = (value, fallback = false) => {
    if (value === undefined || value === null) return fallback;
    const truthy = new Set(['1', 'true', 'yes', 'on', 'sim']);
    return truthy.has(String(value).trim().toLowerCase());
};
const ENABLE_BOT = envBool(process.env.ENABLE_BOT, false);
// ─── CONFIGURAÇÃO DO ENGINE ───
const client = WhatsAppEngine;

async function syncConfig() {
    const backendHost = process.env.BACKEND_HOST || 'backend';
    const url = `http://${backendHost}:${process.env.BACKEND_PORT || 3583}/admin/api/config`;
    
    for (let i = 0; i < 10; i++) {
        try {
            const response = await fetch(url, {
                headers: { 'X-API-KEY': INTERNAL_API_KEY },
                signal: AbortSignal.timeout(5000)
            });
            const data = await response.json();
            if (data.ok) {
                ADMIN_PHONES = (data.configs.admin_phones || '')
                    .split(',')
                    .filter(p => p.trim())
                    .map(p => `${p.trim()}@c.us`);
                GOOGLE_CALENDAR_ID = data.configs.google_calendar_id || 'primary';
                console.log(`[SYNC] ✅ Configurações sincronizadas.`);
                return;
            }
        } catch (e) {
            console.error(`[SYNC] ⏳ Aguardando Backend (${i+1}/10)...`);
            await new Promise(r => setTimeout(r, 4000));
        }
    }
}

// Inicia fluxos (apenas quando o bot estiver habilitado)
if (ENABLE_BOT) {
    syncConfig();
    setInterval(syncConfig, 5 * 60 * 1000);
    initCalendar();
} else {
    console.log('[BOT] Modo on-demand: bot desativado por configuração (ENABLE_BOT=false).');
}

const baseArgs = [
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-features=Translate,OptimizationHints,MediaRouter',
    '--disable-extensions',
    '--disable-component-extensions-with-background-pages',
    '--disable-background-networking',
    '--disable-sync',
    '--metrics-recording-only',
    '--no-pings',
    '--js-flags="--max-old-space-size=256 --stack-size=1024"'
];

let connectionState = ENABLE_BOT ? 'INITIALIZING' : 'DISABLED';
let ADMIN_PHONES = [];
let GOOGLE_CALENDAR_ID = 'primary';

// Eventos WPP
client.on('qr', (qr) => {
    connectionState = 'DISCONNECTED';
    console.log('\n=======================================');
    console.log('📱 ESCANEIE O QR CODE COM O SEU WPP');
    console.log('=======================================\n');
    const qrcodeTerminal = require('qrcode-terminal');
    qrcodeTerminal.generate(qr, { small: true });
});

client.on('ready', () => {
    connectionState = 'CONNECTED';
    console.log('✅ WPP Bot Online e Preparado para Disparos!');
});

client.on('disconnected', (reason) => {
    connectionState = 'DISCONNECTED';
    console.log(`⚠️ Bot desconectado: ${reason}`);
    setTimeout(() => {
        client.initialize().catch((err) => {
            console.error('[BOT] Falha no reconnect:', err.message);
        });
    }, 2500);
});

// Listener duplicado removido para evitar loops e silenciamento de API

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

// Criar interceptadores genéricos para gerir as respostas
async function routeIncomingMessage(phone, text, originalMessageObj, isPollVote = false, parentMessageId = null) {
    if (!text) return;
    
    if (text.toUpperCase() === 'RETOMAR') {
        require('./conversation').updateSessionState(phone, STATES.FUNNEL_PITCH);
        await originalMessageObj.reply("Robô Clienteiro reativado! ✨ Como posso te ajudar a captar mais clientes hoje?");
        return;
    }

    try {
        console.log(`💬 Rx de ${phone}: ${text.substring(0, 50)}...`);
        let chat = null;
        try {
            chat = await originalMessageObj.getChat();
            if (!isPollVote) await chat.sendStateTyping();
        } catch(e){} // se for poll vote as vezes nao tem chat dependendo da lib

        const config = {
            calendarId: GOOGLE_CALENDAR_ID,
            internalApiKey: INTERNAL_API_KEY,
            backendPort: process.env.BACKEND_PORT || 3583
        };
        const responses = await processMessage(phone, text, originalMessageObj, config);

        // Fallback robusto caso getChat falhe (Ex: contas lid ghosted)
        for (const resp of responses) {
            if (!resp) continue;

            if (chat) {
                // Forma Antiga: string ou instancia de Poll direta
                if (typeof resp === 'string' || resp.options) { 
                    await chat.sendStateTyping();
                    await delay(2500); 
                    await chat.sendMessage(resp);
                    continue;
                }

                if (resp.type === 'reaction' && isPollVote && parentMessageId) {
                    try {
                        const msgs = await chat.fetchMessages({limit: 5});
                        const pollMsg = msgs.find(m => m.id.id === parentMessageId);
                        if (pollMsg) {
                             await pollMsg.react(resp.emoji);
                        }
                    } catch (e) { console.error('Error applying custom reaction', e); }
                }

                if (resp.type === 'text' || resp.type === 'poll' || resp.type === 'buttons' || resp.type === 'list') {
                    await chat.sendStateTyping();
                    const variance = Math.floor(Math.random() * 1000) - 500;
                    const finalWait = Math.max(1000, (resp.delay || 2500) + variance); 
                    
                    await delay(finalWait);
                    await chat.clearState();
                    await chat.sendMessage(resp.content);
                }
            } else {
                // FALLBACK SE NÃO TEMOS O OBJETO CHAT PARA FAZER .sendStateTyping()
                if (typeof resp === 'string' || resp.options) { 
                    await delay(2500);
                    await client.sendMessage(`${phone}@c.us`, resp);
                    continue;
                }
                if (resp.type === 'text' || resp.type === 'poll' || resp.type === 'buttons' || resp.type === 'list') {
                    const variance = Math.floor(Math.random() * 1000) - 500;
                    const finalWait = Math.max(1000, (resp.delay || 2500) + variance); 
                    await delay(finalWait);
                    await client.sendMessage(`${phone}@c.us`, resp.content);
                }
            }
        }
    } catch (e) {
        console.error('Erro no processMessage', e);
    }
}

// Receber Mensagem comum
client.on('message', async (message) => {
    if (message.from.includes('@g.us')) return; // ignore groups
    const phone = message.from.replace('@c.us', '');
    const text = message.body || '';
    
    // Alerta de Espelho para Admins
    if (text) {
        for (const admin of ADMIN_PHONES) {
            try {
                // Não alertar a si mesmo caso o admin esteja testando o bot
                if (admin.startsWith(phone)) continue;
                await client.sendMessage(admin, `🚨 *MENSAGEM DE LEAD (${phone}):*\n\n_${text}_`);
            } catch(e) {}
        }
    }

    await routeIncomingMessage(phone, text, message);
});

// Detectar se Humano Pegou (ignorando mensagens de sistema, enquetes, reações)
client.on('message_create', async (msg) => {
    // START: Fix for Loop/Duplicate issue (from original CRM)
    // 1. O óbvio: só nos importamos com mensagens enviadas "por mim"
    if (!msg.fromMe) return;

    // 2. Ignore status updates or group messages
    if (msg.to === 'status@broadcast' || msg.to.includes('@g.us')) return;

    if (msg.type === 'poll_vote') {
        console.log("---- INTERCEPTED POLL VOTE FROM MESSAGE_CREATE ----");
        console.log(msg);
        console.log("---------------------------------------------------");
    }

    // 3. Ignore system template messages, polls, lists, and reactions
    if (msg.type === 'poll_creation' || msg.type === 'poll_vote' || msg.type === 'reaction' || msg.type === 'list_response' || msg.type === 'buttons_response') {
        return;
    }

    // Se passou por TUDO isso, significa que um HUMANO pegou o celular para digitar texto 
    const toPhone = msg.to.replace('@c.us', '');
    const session = require('./conversation').getSession(toPhone);

    // Evita silenciamento por mensagens disparadas via API (Bot)
    if (session.botSending) return;

    if (session.state !== STATES.HUMAN && session.state !== STATES.PDF_SENT && session.state !== STATES.FUNNEL_PITCH) {
        console.log(`👤 Humano digitou no celular (Tipo: ${msg.type}). Parando Bot automações para ${toPhone}`);
        require('./conversation').updateSessionState(toPhone, STATES.HUMAN);
    }
});

client.on('vote_update', async (vote) => {
    console.log("==== VOTE UPDATE FIRED ====");
    console.log(JSON.stringify(vote, null, 2));
    
    // Garante extração limpa do celular, ignorando se veio do subdominio @c.us ou @lid (Linked Business Devices)
    const voterPhone = vote.voter.split('@')[0];
    
    // Obter as opções que ele escolheu agora
    const selectedOptions = vote.selectedOptions; 
    
    if (selectedOptions && selectedOptions.length > 0) {
        const votedText = selectedOptions[0].name;
        console.log(`📊 Seleção capturada de ${voterPhone}: ${votedText}`);
        
        // Alerta de Espelho para Admins (Poll Vote)
        for (const admin of ADMIN_PHONES) {
            try {
                if (admin.startsWith(voterPhone)) continue;
                await client.sendMessage(admin, `🚨 *INTERAÇÃO DE LEAD (${voterPhone}):*\n\nClicou na opção da enquete:\n_${votedText}_`);
            } catch(e) {}
        }

        await routeIncomingMessage(voterPhone, votedText, {
            reply: async (txt) => {
                await client.sendMessage(vote.voter, txt);
            },
            getChat: async () => {
                return await client.getChatById(vote.voter);
            }
        }, true, vote.parentMessage ? vote.parentMessage.id.id : null);
    }
});

// ======= FIM DA CONFIGURAÇÃO DO BOT =======

// ─── MIDDLEWARE DE SEGURANÇA ───
const authenticate = (req, res, next) => {
    const apiKey = req.headers['x-api-key'];
    if (apiKey === INTERNAL_API_KEY) {
        next();
    } else {
        res.status(401).json({ error: 'Unauthorized' });
    }
};

// ─── EXPRESS API PARA O PYTHON ───
app.get('/status', (req, res) => {
    res.json({ status: connectionState, enabled: ENABLE_BOT });
});

// Endpoint para Sincronizar Reagendamento com Google Agenda
app.post('/api/sync-google', async (req, res) => {
    if (!ENABLE_BOT) {
        return res.status(503).json({ error: 'Bot desativado no momento.' });
    }
    const apiKey = req.headers['x-api-key'];
    if (apiKey !== INTERNAL_API_KEY) return res.status(401).json({ error: 'Unauthorized' });

    try {
        const { appointment_id, new_start, phone } = req.body;
        console.log(`🔄 Sincronizando Reagendamento Google: Appt ${appointment_id} -> ${new_start}`);

        // Aqui implementaríamos a lógica de patch no Google Calendar
        // Por enquanto, como prova de conceito, vamos logar. 
        // Em produção, usaríamos calendar.events.patch()
        
        // Notificar o Lead sobre o novo horário
        if (phone) {
            const dateStr = require('dayjs')(new_start).format('DD/MM [às] HH:mm');
            await client.sendMessage(`${phone}@c.us`, `🔔 *Aviso de Reagendamento:*\n\nSeu horário foi atualizado para *${dateStr}h*. Nos vemos lá! ✨`);
        }

        res.json({ ok: true });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

app.post('/api/send-pdf', authenticate, async (req, res) => {
    if (!ENABLE_BOT) {
        return res.status(503).json({ error: 'Bot desativado no momento.' });
    }
    if (connectionState !== 'CONNECTED') {
        return res.status(503).json({ error: 'WhatsApp is not connected yet.' });
    }

    try {
        const { user_phone, user_name, company_name, pdf_path } = req.body;

        if (!user_phone || !pdf_path) {
            return res.status(400).json({ error: 'Missing phone or pdf_path' });
        }

        // Limpa formatação '5511999999999' -> envia para '5511...c.us'
        let rawNum = user_phone.replace(/\D/g, '');
        if (!rawNum.startsWith('55')) {
            rawNum = '55' + rawNum;
        }
        let targetId = `${rawNum}@c.us`;

        if (!fs.existsSync(pdf_path)) {
            return res.status(404).json({ error: 'PDF file not found on disk.' });
        }

        console.log(`🚀 Solicitado Disparo de PDF para ${targetId}`);

        const media = MessageMedia.fromFilePath(pdf_path);
        
        // Envia o arquivo PDF com uma pequena saudacao
        const caption = `Olá ${user_name || 'Estrategista'}! 🚀\n\nAqui está a sua Análise rápida Clienteiro Pro de *${company_name || 'seu negócio'}*.\n\nFizemos a mineração de dados em tempo real, e o relatório acaba de chegar fresco do forno.\nEspero que feche grandes vendas hoje!! 🎉`;
        
        const session = require('./conversation').getSession(rawNum);
        session.botSending = true; // Trava o silenciamento automático

        await client.sendMessage(targetId, media, { caption });

        const { Poll } = require('whatsapp-web.js');
        const pollMsg = new Poll(
            'Espero que o material seja útil para o seu crescimento! 🚀\n\nBut me conta uma coisa... você hoje já possui um processo validado de automação inteligente para converter esses contatos em clientes reais?',
            [
                '✅ SIM, processo liso!', 
                '❌ NÃO, precisamos disso'
            ]
        );
        
        await new Promise(r => setTimeout(r, 3000));
        await client.sendMessage(targetId, pollMsg);

        updateSessionState(rawNum, STATES.FUNNEL_PITCH);
        session.botSending = false; // Destrava

        res.json({ success: true, message: 'PDF and Pitch Scheduled to send.' });
    } catch (e) {
        console.error('Erro no Disparo POST /send-pdf:', e);
        res.status(500).json({ error: e.message });
    }
});

// ─── POST /webhook/evolution ───
// Receptor principal de mensagens quando no modo Evolution API
app.post('/webhook/evolution', async (req, res) => {
    try {
        const payload = req.body;
        const config = {
            instance: process.env.EVOLUTION_INSTANCE || 'clienteiro_pro'
        };

        const event = payload?.event?.toLowerCase();
        // Eventos de mensagem da Evolution API v2.x
        if (event === 'messages.upsert' || event === 'messages.update' || event === 'message.create') {
            const data = payload.data;
            const messages = data.messages || (data.message ? [data.message] : []);

            for (const msg of messages) {
                if (msg.key?.fromMe) continue; // Ignora se enviada por nós

                const remoteJid = msg.key?.remoteJid || '';
                if (remoteJid.includes('@g.us') || remoteJid === 'status@broadcast') continue;

                const phone = remoteJid.split('@')[0];
                const text = msg.message?.conversation || 
                             msg.message?.extendedTextMessage?.text || 
                             msg.message?.imageMessage?.caption || '';

                if (!text && !msg.message?.imageMessage) continue;

                // Mock do objeto Message do WWebJS para reutilizar routeIncomingMessage
                const mockMessage = {
                    from: `${phone}@c.us`,
                    body: text,
                    fromMe: false,
                    hasMedia: !!msg.message?.imageMessage,
                    type: msg.message?.imageMessage ? 'image' : 'chat',
                    timestamp: msg.messageTimestamp,
                    id: { id: msg.key?.id, _serialized: msg.key?.id },
                    getChat: async () => ({
                        sendStateTyping: async () => {}, // No-op em API
                        sendMessage: async (txt) => client.sendMessage(`${phone}@c.us`, txt)
                    }),
                    reply: async (txt) => client.sendMessage(`${phone}@c.us`, txt)
                };

                console.log(`[EVO] Webhook Rx de ${phone}: ${text.substring(0, 30)}`);
                client.emit('message', mockMessage);
            }
        }
        res.status(200).send('OK');
    } catch (err) {
        console.error('[EVO] Erro no Webhook:', err.message);
        res.status(500).send('Internal Error');
    }
});


app.listen(PORT, () => {
    console.log(`⚡ WPP Bot API ouvindo na porta ${PORT}`);
    console.log(`⚡ Modo: ${process.env.WHATSAPP_PROVIDER || 'wwebjs'}`);
    if (ENABLE_BOT) {
        client.initialize().catch(err => console.error('Error on init:', err));
    } else {
        console.log('[BOT] Inicialização do WhatsApp ignorada (ENABLE_BOT=false).');
    }
});

// --- GRACEFUL SHUTDOWN ---
const shutdown = async (signal) => {
    console.log(`\n[BOT] Recebido ${signal}. Encerrando de forma graciosa...`);
    try {
        if (client) {
            await client.destroy();
            console.log('[BOT] Client destruído.');
        }
    } catch (e) {
        console.error('[BOT] Erro ao destruir:', e);
    }
    process.exit(0);
};

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));
