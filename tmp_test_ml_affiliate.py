"""
Teste: Gerar link de afiliado do Mercado Livre via API
Produto de teste: Monitor Philco - MLB58912730
"""
import requests

ACCESS_TOKEN = "APP_USR-7533256838927611-030111-a61ca01827c97164600125b0afef3bc1-3167600472"
TAG = "codepysystems"
MATT_TOOL = "13013217"  # ID do canal de afiliado (visto no link gerado)

ITEM_ID = "MLB58912730"
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

print("=" * 60)
print("TESTE 1: Buscar dados do produto via API")
print("=" * 60)
r = requests.get(f"https://api.mercadolibre.com/items/{ITEM_ID}", headers=HEADERS)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"Título: {data.get('title')}")
    print(f"Permalink: {data.get('permalink')}")
    permalink = data.get('permalink', '')
else:
    print(f"Erro: {r.text[:200]}")
    permalink = f"https://www.mercadolivre.com.br/p/{ITEM_ID}"

print()
print("=" * 60)
print("TESTE 2: Tentar endpoint de links de afiliado")
print("=" * 60)

# Tenta endpoint de tracking/afiliado
endpoints = [
    f"https://api.mercadolibre.com/items/{ITEM_ID}/tracking_url",
    f"https://api.mercadolibre.com/affiliate/links",
    f"https://api.mercadolibre.com/social/links",
]

for ep in endpoints:
    try:
        r2 = requests.get(ep, headers=HEADERS)
        print(f"[{r2.status_code}] {ep}")
        if r2.status_code == 200:
            print(f"  ✅ RESPOSTA: {r2.text[:300]}")
        else:
            print(f"  Resposta: {r2.text[:100]}")
    except Exception as e:
        print(f"  Erro: {e}")

print()
print("=" * 60)
print("TESTE 3: Construir link com params básicos (sem ref criptografado)")
print("=" * 60)
# Testa se o link funciona apenas com matt_tool (sem o ref gigante)
link_simples = f"{permalink}?matt_word={TAG}&matt_tool={MATT_TOOL}"
print(f"Link construído: {link_simples}")
r3 = requests.get(link_simples, allow_redirects=False, timeout=5)
print(f"Status da URL: {r3.status_code} (301/302 = redireciona OK, 200 = funciona direto)")
