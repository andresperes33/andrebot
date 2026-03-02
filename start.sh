#!/bin/bash

# ==================================================
# Script de Inicialização para Produção (EasyPanel)
# ==================================================

# 1. Rodar migrações do banco de dados (Postgres)
echo "🚀 Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

# 2. Iniciar o Monitor de Ofertas (Processo Principal)
echo "🔍 Iniciando Monitor do zFinnY..."
python manage.py monitor_offers

# O André Bot (run_bot) está desativado pois o monitor já envia para Telegram + WhatsApp
# Para reativar: descomentar abaixo e adicionar & no monitor_offers acima
# python manage.py run_bot
