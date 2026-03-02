import requests
import json

# Tentando listar todos os grupos com timeout maior
url = "https://andrebot-evolution-api.m9hodh.easypanel.host/group/fetchAllGroups/andrebot?getParticipants=false"
headers = {
    "apikey": "49408D499830-4342-8C74-AD3A629AE6B2"
}

try:
    print(f"Buscando grupos para a instância andrebot...")
    response = requests.get(url, headers=headers, timeout=30)
    
    if response.status_code == 200:
        groups = response.json()
        target_name = "Alerta Tech Brasil"
        
        # Caso a resposta seja uma lista direta ou um objeto com 'data'
        groups_list = []
        if isinstance(groups, list):
            groups_list = groups
        elif isinstance(groups, dict):
            groups_list = groups.get('data') or groups.get('groups') or groups.get('description') or []
            if not isinstance(groups_list, list) and isinstance(groups, dict):
                # Alguns casos retornam o objeto da instância
                groups_list = [groups]

        found = False
        for g in groups_list:
            if isinstance(g, dict):
                name = g.get('subject') or g.get('name')
                jid = g.get('id') or g.get('jid')
                if name and target_name.lower() in name.lower():
                    print(f"\n✅ GRUPO ENCONTRADO!")
                    print(f"Nome: {name}")
                    print(f"JID: {jid}")
                    found = True
                    break
        
        if not found:
            print(f"\n❌ Grupo '{target_name}' não encontrado na lista atual.")
            # Printa os nomes dos grupos encontrados para debug (ajuda o usuário a escolher)
            print("\nGrupos disponíveis encontrados:")
            for g in groups_list:
                if isinstance(g, dict):
                    print(f"- {g.get('subject') or g.get('name')} (ID: {g.get('id') or g.get('jid')})")
    
    else:
        print(f"Erro na API (Status {response.status_code}): {response.text}")

except Exception as e:
    print(f"Erro: {e}")
