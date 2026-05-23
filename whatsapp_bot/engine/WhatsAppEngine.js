const EventEmitter = require('events');
const WWebJSProvider = require('./providers/WWebJSProvider');
const EvolutionProvider = require('./providers/EvolutionProvider');

class WhatsAppEngine extends EventEmitter {
    constructor() {
        super();
        this.provider = null;
        this.providerType = process.env.WHATSAPP_PROVIDER || 'wwebjs';
    }

    async initialize(tenantId = 'default') {
        console.log(`[WhatsAppEngine] Inicializando provedor: ${this.providerType}`);

        if (this.providerType === 'evolution') {
            this.provider = new EvolutionProvider();
        } else {
            this.provider = new WWebJSProvider();
        }

        // Repassar eventos do provedor para a Engine
        this.provider.on('qr', (qr) => this.emit('qr', qr));
        this.provider.on('auth_failure', (msg) => this.emit('auth_failure', msg));
        this.provider.on('ready', () => {
            this.info = this.provider.info;
            this.emit('ready');
        });
        this.provider.on('message', (msg) => this.emit('message', msg));
        this.provider.on('disconnected', (reason) => this.emit('disconnected', reason));

        await this.provider.initialize(tenantId);
    }

    async sendMessage(chatId, content, options = {}) {
        if (!this.provider) throw new Error('Provedor não inicializado');
        return await this.provider.sendMessage(chatId, content, options);
    }

    async logout() {
        if (this.provider) return await this.provider.logout();
    }
}

module.exports = new WhatsAppEngine();
