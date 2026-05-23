const axios = require('axios');
const EventEmitter = require('events');

class EvolutionProvider extends EventEmitter {
    constructor() {
        super();
        this.apiUrl = process.env.EVOLUTION_API_URL;
        this.apiKey = process.env.EVOLUTION_API_KEY;
        this.instance = process.env.EVOLUTION_INSTANCE || 'clienteiro_pro';
        this.info = null;
    }

    async initialize() {
        console.log(`[EvolutionProvider] Inicializando modo LEVE para instância: ${this.instance}`);
        
        // No modo Evolution, o robô atua como um servidor de Webhook.
        // O "ready" aqui sinaliza que a Engine já pode aceitar requisições.
        setTimeout(() => {
            this.info = { wid: { user: this.instance } };
            this.emit('ready');
        }, 1000);
    }

    async sendMessage(chatId, content, options = {}) {
        const phone = chatId.split('@')[0];
        try {
            console.log(`[EvolutionProvider] Enviando mensagem para ${phone}`);
            
            const response = await axios.post(`${this.apiUrl}/message/sendText/${this.instance}`, {
                number: phone,
                text: content,
                delay: 1200,
                linkPreview: true
            }, {
                headers: { 'apikey': this.apiKey }
            });

            return { id: { _serialized: response.data.key?.id || Date.now().toString() } };
        } catch (err) {
            console.error('[EvolutionProvider] Erro ao enviar mensagem:', err.response?.data || err.message);
            throw err;
        }
    }

    async logout() {
        try {
            await axios.post(`${this.apiUrl}/instance/logout/${this.instance}`, {}, {
                headers: { 'apikey': this.apiKey }
            });
        } catch (err) {
            console.error('[EvolutionProvider] Erro ao deslogar:', err.message);
        }
    }
}

module.exports = EvolutionProvider;
