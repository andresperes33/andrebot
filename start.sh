#!/bin/bash

# ==================================================
# Script de Inicialização para Produção (EasyPanel)
# ==================================================

# 1. Rodar migrações do banco de dados (Postgres)
echo "🚀 Aplicando migrações do banco de dados..."
python manage.py migrate --noinput

# 2. Iniciar o bot
echo "🤖 Iniciando o bot do Telegram..."
python manage.py run_bot
