import asyncio
import os
from telethon import TelegramClient
from telethon.sessions import StringSession

# Configurações do seu app (já preenchidas com seus dados)
API_ID = 38406719
API_HASH = 'aec41e4ed48d59ba62816f01798be347'

async def main():
    print("\n🚀 INICIANDO GERADOR DE SESSÃO PERSISTENTE")
    print("------------------------------------------")
    print("Este script vai gerar uma 'String Session' para o seu bot.")
    print("Isso resolve o problema de o bot pedir código de login no EasyPanel.\n")
    
    try:
        async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
            session_string = client.session.save()
            print("\n" + "✅"*25)
            print("SUA CHAVE DE SESSÃO FOI GERADA!")
            print("COPIE O CÓDIGO ABAIXO (TUDO, SEM ESPAÇOS):")
            print("="*60)
            print(f"{session_string}")
            print("="*60)
            print("\nPRÓXIMOS PASSOS:")
            print("1. Copie o código acima.")
            print("2. Vá no seu EasyPanel -> Variáveis de Ambiente (.env).")
            print("3. Adicione a linha: TELEGRAM_STRING_SESSION = seu_codigo_aqui")
            print("4. Salve e dê Restart no app.")
            print("5. O app ficará VERDE e não pedirá mais login! 🚀")
            print("✅"*25 + "\n")
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        print("Certifique-se de que você digitou o código do Telegram corretamente.")

if __name__ == "__main__":
    # Verifica se telethon está instalado
    try:
        import telethon
    except ImportError:
        print("\n❌ ERRO: Biblioteca 'telethon' não encontrada.")
        print("Execute: pip install telethon")
        exit()
        
    asyncio.run(main())
