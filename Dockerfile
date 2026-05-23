FROM python:3.11-slim

# 1. Instala dependências de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    curl \
    gnupg \
    wget \
    tini \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Instala o Google Chrome
RUN wget -qO- https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 3. Cria usuário não-root para segurança (Zero Trust)
RUN groupadd -g 1000 clienteiro && \
    useradd -u 1000 -g clienteiro -m -s /bin/bash clienteiro

WORKDIR /app

# Prepara diretórios de escrita antes de mudar para usuário comum
RUN mkdir -p /app/data /app/reports && \
    chown -R clienteiro:clienteiro /app

# 4. Cache de dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia o código e ajusta propriedade
COPY --chown=clienteiro:clienteiro . .

# 6. Variáveis de ambiente
ENV FLASK_APP=app.py
ENV PORT=3583
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER clienteiro

EXPOSE 3583

# 7. Execução (Gunicorn)
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:3583", "app:app", "--timeout", "120", "--log-level", "info"]
