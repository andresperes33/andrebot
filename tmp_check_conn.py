import requests

url = "https://andrebot-evolution-api.m9hodh.easypanel.host/instance/connectionStatus/andrebot"
headers = {
    "apikey": "49408D499830-4342-8C74-AD3A629AE6B2"
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    print(response.json())
except Exception as e:
    print(f"Erro: {e}")
