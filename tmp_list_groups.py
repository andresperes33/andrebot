import requests
import json

url = "https://andrebot-evolution-api.m9hodh.easypanel.host/group/fetchAllGroups/andrebot"
headers = {
    "apikey": "49408D499830-4342-8C74-AD3A629AE6B2"
}

try:
    response = requests.get(url, headers=headers, timeout=15)
    print(f"Status Code: {response.status_code}")
    groups = response.json()
    
    # Se groups for uma lista direta ou estiver dentro de um objeto
    if isinstance(groups, dict):
        # Algumas versões da Evolution API retornam dentro de um campo
        groups_list = groups.get('data') or groups.get('groups') or groups
    else:
        groups_list = groups

    print(json.dumps(groups_list, indent=2))
except Exception as e:
    print(f"Erro: {e}")
