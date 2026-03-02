import requests

url = "https://andrebot-evolution-api.m9hodh.easypanel.host/message/sendText/andrebot"
token = "49408D499830-4342-8C74-AD3A629AE6B2"
jid = "120363425112619406@g.us"

headers = {
    "apikey": token,
    "Content-Type": "application/json"
}

payload = {
    "number": jid,
    "text": "🚀 Teste de Conexão: O robô está tentando falar com o WhatsApp!",
    "options": {
        "delay": 0,
        "presence": "composing"
    }
}

try:
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Resposta: {response.text}")
except Exception as e:
    print(f"Erro: {e}")
