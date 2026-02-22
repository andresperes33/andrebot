# Bot Telegram de Afiliados (Django)

Este projeto é um bot do Telegram construído com Django que converte links enviados para links de afiliado (ex: Shopee) e os posta automaticamente em um grupo.

## Pré-requisitos

- Python 3.10+
- Token do Bot do Telegram (obtido através do @BotFather)
- ID do Grupo do Telegram onde o bot postará as ofertas

## Instalação

1. O projeto já possui uma `venv`. Ative-a:
   - No Windows: `.\venv\Scripts\activate`
   - No Linux/Mac: `source venv/bin/activate`

2. Instale as dependências (caso não tenha feito):
   ```bash
   pip install django python-telegram-bot python-dotenv requests
   ```

3. Configure o arquivo `.env` na raiz do projeto:
   ```env
   TELEGRAM_BOT_TOKEN=seu_token_aqui
   TELEGRAM_GROUP_ID=seu_id_do_grupo_aqui
   SHOPEE_AFFILIATE_ID=seu_id_de_rastreamento_aqui
   ```

## Como Rodar

Para iniciar o bot, execute o comando de gerenciamento customizado:

```bash
python manage.py run_bot
```

## Como Usar

1. Adicione o bot ao seu grupo e torne-o administrador para que ele tenha permissão de postar mensagens.
2. Envie um link (ex: um produto da Shopee) diretamente para o chat privado do bot.
3. O bot converterá o link e postará no grupo configurado.

## Estrutura do Projeto

- `bot/services.py`: Contém a lógica de conversão de links.
- `bot/telegram_bot.py`: Contém os handlers do Telegram.
- `bot/management/commands/run_bot.py`: Comando para integrar o bot ao ciclo de vida do Django.
