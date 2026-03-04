#!/bin/bash

# ==================================================
# Script de Inicialização para Produção (EasyPanel)
# ==================================================

# 1. Rodar migrações do banco de dados (Postgres)
echo "🚀 Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

# 2. Iniciar o Bot de Alertas em background
echo "🤖 Iniciando Bot de Alertas (@andreindica_bot)..."
python manage.py run_alert_bot &

# 3. Iniciar o Monitor de Ofertas (Processo Principal)
echo "🔍 Iniciando Monitor do zFinnY..."
python manage.py monitor_offers
