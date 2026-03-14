#!/bin/bash

# ==================================================
# Script de Inicialização para Produção (EasyPanel)
# ==================================================

# 1. Rodar migrações do banco de dados (Postgres)
echo "🚀 Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

# 2. Coletar arquivos estáticos
echo "📁 Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

# 3. Iniciar servidor web (Gunicorn) em background
echo "🌐 Iniciando servidor web na porta 8000..."
gunicorn setup.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120 &

# 4. Iniciar o Bot de Alertas em background
echo "🤖 Iniciando Bot de Alertas (@alertas_andre_bot)..."
python manage.py run_alert_bot &

# 5. Iniciar o Monitor de Ofertas (Processo Principal)
echo "🔍 Iniciando Monitor do zFinnY..."
python manage.py monitor_offers
