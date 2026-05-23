const { Client, LocalAuth } = require('whatsapp-web.js');
const EventEmitter = require('events');

class WWebJSProvider extends EventEmitter {
    constructor() {
        super();
        this.client = null;
        this.info = null;
    }

    async initialize() {
        console.log('[WWebJSProvider] Inicializando com Puppeteer...');
        
        this.client = new Client({
            authStrategy: new LocalAuth(),
            puppeteer: {
                headless: true,
                args: [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ]
            }
        });

        this.client.on('qr', (qr) => this.emit('qr', qr));
        this.client.on('ready', () => {
            this.info = this.client.info;
            console.log('[WWebJSProvider] Cliente pronto!');
            this.emit('ready');
        });
        this.client.on('message', (msg) => this.emit('message', msg));
        this.client.on('auth_failure', (msg) => this.emit('auth_failure', msg));
        this.client.on('disconnected', (reason) => this.emit('disconnected', reason));

        await this.client.initialize();
    }

    async sendMessage(chatId, content, options = {}) {
        return await this.client.sendMessage(chatId, content, options);
    }

    async logout() {
        if (this.client) await this.client.logout();
    }
}

module.exports = WWebJSProvider;
