#!/bin/bash

# --- 🚀 Script de Setup "Clienteiro Elite" para VPS Linux ---
# Use: chmod +x setup_vps.sh && ./setup_vps.sh

echo "📦 Iniciando instalação do Clienteiro em ambiente de produção..."

# 1. Atualizar Sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar Dependências de Sistema
sudo apt install -y python3-pip python3-venv git curl libpq-dev

# 3. Preparar o Ambiente Python
python3 -m venv venv
source venv/bin/activate

# 4. Instalar Dependências Python
pip install --upgrade pip
pip install -r requirements.txt

# 5. Instalar Playwright & Navegadores
playwright install chromium
playwright install-deps

# 6. Instalar Node.js & PM2 (Process Manager)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2

# 7. Instalar Dependências do Bot (Node.js)
if [ -d "whatsapp_bot" ]; then
    echo "🤖 Instalando dependências do Bot WhatsApp..."
    cd whatsapp_bot
    npm install
    cd ..
fi

# 8. Inicializar Banco de Dados (Schema migration)
echo "🗄️ Inicializando Schema do Supabase..."
python3 core/db_manager.py

# 9. Subir Serviços com PM2
echo "🔥 Subindo serviços no PM2..."
pm2 start app.py --name "clienteiro-backend" --interpreter ./venv/bin/python3

if [ -f "whatsapp_bot/bot.js" ]; then
    pm2 start whatsapp_bot/bot.js --name "clienteiro-bot"
fi

pm2 save
pm2 startup

echo "✅ Setup concluído! O back-end está rodando na porta 3583."
echo "⚠️  Lembre-se de configurar seu .env com DEBUG=False e chaves reais."
