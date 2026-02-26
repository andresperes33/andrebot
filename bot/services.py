import re
import time
import hashlib
import json
import requests
from django.conf import settings


def get_product_info(url):
    """
    Extrai informações do produto da URL e da página (Shopee ou AliExpress).
    """
    name = None
    image_url = None
    price = None

    try:
        # ── Nome via Slug (Shopee) ────────────────────────────────────────
        if 'shopee' in url:
            slug_match = re.search(r'shopee\.com\.br/([^/?]+?)(?:-i\.\d+\.\d+)', url)
            if slug_match:
                slug = slug_match.group(1)
                name = slug.replace('-', ' ').title()

        # ── Scraping Geral (Meta tags e Preço) ────────────────────────────
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9",
        }
        try:
            # Segue redirecionamentos para chegar na página real do produto
            resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            html = resp.text
            final_url = resp.url

            # Nome via meta tag (og:title ou twitter:title)
            if not name:
                meta_name = re.search(r'<meta[^>]+property=["\'](?:og:title|twitter:title)["\'][^>]+content=["\'](.*?)["\']', html)
                if meta_name:
                    name = meta_name.group(1).split('|')[0].strip()

            # Preço Shopee (centavos)
            if 'shopee' in final_url:
                price_matches = re.findall(r'"price":(\d{7,})', html)
                if price_matches:
                    price_val = int(price_matches[0]) / 100000
                    price = f"R$ {price_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            # Preço AliExpress (Geralmente em meta ou json)
            elif 'aliexpress' in final_url:
                price_match = re.search(r'["\']currencyCode["\']:["\']BRL["\'],["\']value["\']:(\d+\.?\d*)', html)
                if not price_match:
                    # Alternativa para preço no AliExpress
                    price_match = re.search(r'["\']amount["\']:["\'](\d+\.\d+)["\']', html)
                
                if price_match:
                    price_val = float(price_match.group(1))
                    price = f"R$ {price_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            # Preço Mercado Livre
            elif 'mercadolivre' in final_url:
                price_match = re.search(r'<meta[^>]+itemprop=["\']price["\'][^>]+content=["\'](\d+\.?\d*)["\']', html)
                if price_match:
                    price_val = float(price_match.group(1))
                    price = f"R$ {price_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            # Preço Amazon
            elif 'amazon' in final_url:
                # Tenta várias classes comuns de preço na Amazon
                price_match = re.search(r'class=["\']a-offscreen["\']>(.*?)</span>', html)
                if price_match:
                    price = price_match.group(1).strip()
                else:
                    price_match = re.search(r'class=["\']a-price-whole["\']>(.*?)</span>', html)
                    if price_match:
                        price = f"R$ {price_match.group(1).strip()}"

                    price = f"R$ {price_val}"

            # Preço Magalu
            elif 'magazineluiza.com.br' in final_url or 'magalu.com' in final_url:
                # Tenta JSON de preço
                price_match = re.search(r'["\']price["\']:["\']?(\d+\.?\d*)["\']?', html)
                if not price_match:
                    price_match = re.search(r'class=["\']sc-[^>]+price-value["\']>(.*?)</span>', html)
                
                if price_match:
                    price_val = price_match.group(1).replace('R$', '').strip()
                    price = f"R$ {price_val}"

            # Imagem: tenta várias tags comuns (og:image, twitter:image, image_src)
            img_patterns = [
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\']+)["\']',
                r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\'](https?://[^"\']+)["\']',
                r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\'](https?://[^"\']+)["\']',
                r'["\']image["\']:["\'](https?://[^"\']+)["\']'
            ]
            
            for pattern in img_patterns:
                img_match = re.search(pattern, html)
                if img_match:
                    image_url = img_match.group(1).strip()
                    # Limpeza para AliExpress
                    if 'aliexpress' in final_url and '_' in image_url:
                        image_url = image_url.split('_')[0]
                        if not image_url.endswith(('.jpg', '.png', '.webp')):
                            image_url += '.jpg'
                    # Limpeza para Mercado Livre (Alta Resolução)
                    if 'mercadolivre' in final_url and '-O.jpg' in image_url:
                        image_url = image_url.replace('-O.jpg', '-F.jpg')
                    # Limpeza para Amazon (Pega imagem maior)
                    if 'amazon' in final_url and '._AC_' in image_url:
                        image_url = re.sub(r'\._AC_.*_\.', '.', image_url)
                    # Limpeza para Kabum (Geralmente ja vem em boa resolucao)
                    if 'kabum.com.br' in final_url and '?' in image_url:
                        image_url = image_url.split('?')[0]
                    break

        except Exception as page_err:
            print(f"Aviso na página: {page_err}")

    except Exception as e:
        print(f"Erro get_product_info: {e}")

    print(f"Produto: {name} | Preço: {price} | Imagem: {bool(image_url)}")
    return name, image_url, price


import urllib.parse

def convert_to_affiliate_link(url, final_url=None):
    """
    Decide qual API usar com base na URL.
    """
    if 'shopee.com.br' in url or 's.shopee' in url:
        return convert_shopee_link(url)
    elif 'aliexpress.com' in url or 's.click.aliexpress' in url:
        return convert_aliexpress_link(url)
    elif 'amazon.com.br' in url or 'amzn.to' in url:
        return convert_amazon_link(url)
    elif 'mercadolivre.com' in url or 'mlstatic.com' in url or 'mercadolivre.com.br' in url:
        return convert_mercado_livre_link(url)
    elif 'kabum.com.br' in url or 'tidd.ly' in url:
        return convert_awin_link(url, merchant_id='17729') # Kabum MID padrao
    elif 'magazineluiza.com.br' in url or 'magalu.com' in url or 'mgl.io' in url or 'divulgador.magalu.com' in url:
        return convert_magalu_link(url)
    return None


def convert_awin_link(url, merchant_id='17729'):
    """
    Gera link de afiliado Awin. Limpa a URL da Kabum para evitar bugs de tela preta
    e links gigantes com rastreios de terceiros.
    """
    publisher_id = getattr(settings, 'AWIN_PUBLISHER_ID', '1670083')
    api_token = getattr(settings, 'AWIN_API_TOKEN', None)

    # 1. Expandir links curtos (tidd.ly) para pegar a URL real
    if 'tidd.ly' in url:
        try:
            resp = requests.get(url, allow_redirects=True, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            url = resp.url
        except Exception as e:
            print(f"Awin: Erro ao expandir: {e}")

    # 2. LIMPEZA PROFUNDA: Extrair apenas o link essencial da Kabum
    # Aceita tanto /produto/ID/NOME quanto apenas /produto/ID
    kabum_match = re.search(r'(https?://(?:www\.)?kabum\.com\.br/produto/\d+(?:/[^/?\s]+)?)', url)
    if kabum_match:
        url = kabum_match.group(1)
    elif 'kabum.com.br' in url:
        url = url.split('?')[0]

    # 3. Tentar encurtar via API (Tidd.ly)
    if api_token:
        try:
            endpoint = f"https://api.awin.com/publishers/{publisher_id}/link-generator"
            headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
            payload = {
                "destinationUrl": url,
                "advertiserId": int(merchant_id),
                "shorten": True
            }
            response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
            res_data = response.json()
            short_url = res_data.get("shortUrl")
            if short_url:
                print(f"Awin API Sucesso: {short_url}")
                return short_url
            else:
                print(f"Awin API falhou em encurtar: {res_data}")
        except Exception as e:
            print(f"Erro Awin API: {e}")

    # 4. Fallback: Deep Link (Formato hibrido para evitar home e tela preta)
    # Mantemos o https:// visível e codificamos o restante do link
    if url.startswith('https://'):
        url_part = url.replace('https://', '', 1)
        encoded_url = 'https://' + urllib.parse.quote(url_part, safe='')
    else:
        encoded_url = urllib.parse.quote(url, safe='')
        
    return f"https://www.awin1.com/cread.php?awinmid={merchant_id}&awinaffid={publisher_id}&platform=dl&ued={encoded_url}"


def convert_magalu_link(url):
    """
    Gera link de afiliado Parceiro Magalu (magazinevoce) de forma robusta.
    """
    magalu_id = getattr(settings, 'MAGALU_ID', 'in_1546179')
    
    # Se for link curto, expande (mgl.io ou divulgador.magalu.com ou magalu.com)
    if any(domain in url for domain in ['mgl.io', 'divulgador.magalu.com', 'magalu.com/']):
        try:
            resp = requests.get(url, allow_redirects=True, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
            url = resp.url
        except Exception as e:
            print(f"Magalu Expansão Erro: {e}")

    # Lista de tentativas para pegar o ID e o Slug
    # 1. Tenta padrão de link longo: magazineluiza.com.br/SLUG/p/ID/
    match_long = re.search(r'(?:magazineluiza\.com\.br|magalu\.com)/([^/]+)/p/([a-zA-Z0-9]+)', url)
    if match_long:
        slug, pid = match_long.group(1), match_long.group(2)
        return f"https://www.magazinevoce.com.br/{magalu_id}/{slug}/p/{pid}/"

    # 2. Tenta padrão apenas com ID: /p/ID/
    match_p_only = re.search(r'/p/([a-zA-Z0-9]+)', url)
    if match_p_only:
        pid = match_p_only.group(1)
        # Tenta pegar um slug da URL se existir, senao usa 'p'
        slug_candidates = [s for s in url.split('/') if s and s not in ['p', 'produto', 'https:', 'www.magazineluiza.com.br', 'magalu.com']]
        slug = slug_candidates[0] if slug_candidates else "produto"
        return f"https://www.magazinevoce.com.br/{magalu_id}/{slug}/p/{pid}/"

    # 3. Tenta padrão antigo: /produto/ID
    match_old = re.search(r'/produto/([a-zA-Z0-9]+)', url)
    if match_old:
        pid = match_old.group(1)
        return f"https://www.magazinevoce.com.br/{magalu_id}/produto/p/{pid}/"

    # 4. Caso extremo: tenta pegar qualquer código alfanumérico de 10 caracteres que pareça um ID Magalu
    # IDs da Magalu geralmente tem 10 caracteres como 'kj38f5f87b'
    potential_ids = re.findall(r'/([a-z0-9]{10})/', url)
    if potential_ids:
        return f"https://www.magazinevoce.com.br/{magalu_id}/produto/p/{potential_ids[0]}/"

    return f"https://www.magazinevoce.com.br/{magalu_id}/"


def convert_amazon_link(url):
    """
    Gera link de afiliado Amazon injetando a TAG.
    """
    tag = getattr(settings, 'AMAZON_ASSOCIATE_TAG', 'andreindica00-20')
    
    # Se for link curto da Amazon, precisamos expandir para pegar o ID do produto
    if 'amzn.to' in url:
        try:
            resp = requests.get(url, allow_redirects=True, timeout=5)
            url = resp.url
        except:
            pass
            
    # Limpa a URL de tags antigas e adiciona a sua
    clean_url = url.split('?')[0]
    return f"{clean_url}?tag={tag}"


def convert_mercado_livre_link(url):
    """
    Gera link de afiliado oficial do Mercado Livre via API /affiliates/links.
    Usa Access Token OAuth2 e a Tag configurados no .env.
    """
    access_token = getattr(settings, 'MERCADO_LIVRE_ACCESS_TOKEN', None)
    tag = getattr(settings, 'MERCADO_LIVRE_TAG', 'pean3412407')

    if not access_token or not tag:
        print("ML: access_token ou tag nao configurados.")
        return None

    # Expande links curtos (mercadolivre.com/sec/...) antes de enviar para a API
    try:
        if '/sec/' in url or 'mercadolivre.com/s/' in url:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, allow_redirects=True)
            url = resp.url.split('?')[0]
            print(f"ML: URL expandida para: {url}")
    except Exception as e:
        print(f"ML: Erro ao expandir URL: {e}")

    endpoint = "https://api.mercadolibre.com/affiliates/links"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "url": url,
        "tag_label": tag
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        data = response.json()
        print(f"ML API Response: {data}")
        # Tenta pegar o link em diferentes campos possíveis da resposta
        affiliate_url = data.get("link") or data.get("short_url") or data.get("url")
        if affiliate_url:
            return affiliate_url
        print(f"ML: API nao retornou link. Resposta completa: {data}")
        return None
    except Exception as e:
        print(f"ML API Erro: {e}")
        return None


def convert_shopee_link(url):
    """API Shopee"""
    app_id = settings.SHOPEE_APP_ID
    app_secret = settings.SHOPEE_SECRET
    if not app_id or not app_secret: return None

    endpoint = "https://open-api.affiliate.shopee.com.br/graphql"
    timestamp = int(time.time())
    graphql_query = 'mutation{generateShortLink(input:{originUrl:"' + url + '"}){shortLink}}'
    query = {"query": graphql_query}
    body = json.dumps(query, separators=(',', ':'))
    payload = f"{app_id}{timestamp}{body}{app_secret}"
    signature = hashlib.sha256(payload.encode('utf-8')).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id},Timestamp={timestamp},Signature={signature}"
    }

    try:
        response = requests.post(endpoint, headers=headers, data=body)
        res = response.json().get('data', {}).get('generateShortLink', {})
        return res.get('shortLink')
    except:
        return None


def convert_aliexpress_link(url):
    """API AliExpress"""
    app_key = settings.ALIEXPRESS_APP_KEY
    app_secret = settings.ALIEXPRESS_APP_SECRET
    tracking_id = settings.ALIEXPRESS_TRACKING_ID
    if not app_key or not app_secret: return None

    endpoint = "https://api-sg.aliexpress.com/sync"
    params = {
        "app_key": app_key,
        "format": "json",
        "method": "aliexpress.affiliate.link.generate",
        "sign_method": "md5",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "v": "2.0",
        "promotion_link_type": "0",
        "source_values": url,
        "tracking_id": tracking_id
    }

    # Gerar Assinatura MD5 AliExpress
    sorted_keys = sorted(params.keys())
    sign_str = app_secret
    for key in sorted_keys:
        sign_str += f"{key}{params[key]}"
    sign_str += app_secret
    params["sign"] = hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

    try:
        response = requests.get(endpoint, params=params)
        data = response.json()
        result = data.get("aliexpress_affiliate_link_generate_response", {}).get("resp_result", {}).get("result", {})
        links = result.get("promotion_links", {}).get("promotion_link", [])
        if links:
            return links[0].get("promotion_link")
    except Exception as e:
        print(f"Erro AliExpress API: {e}")
        return None


def extract_links(text):
    return re.findall(r'(https?://\S+)', text)
