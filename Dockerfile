# =============================================
# DOCKERFILE — Bot de Afiliados Telegram
# Deploy via EasyPanel / Hostinger VPS
# =============================================

# Imagem base Python enxuta
FROM python:3.13-slim

# Evita que o Python crie arquivos .pyc e desabilita o buffer de saída
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Diretório de trabalho dentro do container
WORKDIR /app

# Instala dependências do sistema (necessárias para o Postgres e compilação)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências Python primeiro (aproveita cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Coleta arquivos estáticos
RUN python manage.py collectstatic --noinput

# Dá permissão de execução para o script de inicialização
RUN chmod +x /app/start.sh

# Aplica migrações e inicia o bot via script
CMD ["/bin/bash", "/app/start.sh"]
