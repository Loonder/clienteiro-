FROM node:20-slim

WORKDIR /app

# Instala apenas o básico essencial (curl para healthchecks)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

EXPOSE 3582

CMD ["node", "bot.js"]
