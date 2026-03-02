import requests
import json

url = "https://andrebot-evolution-api.m9hodh.easypanel.host/group/fetchAllGroups/andrebot?getParticipants=false"
headers = {
    "apikey": "49408D499830-4342-8C74-AD3A629AE6B2"
}

try:
    response = requests.get(url, headers=headers, timeout=15)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        groups = response.json()
        print(json.dumps(groups, indent=2))
    else:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Erro: {e}")
