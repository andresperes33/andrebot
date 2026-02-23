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
    # Mercado Livre: Desativado conversão automática para evitar links inexistentes. 
    # O bot apenas extrairá infos no handle_message.
    return None


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
    Simula o link de redirecionamento do ML Criadores usando a TAG.
    Usa a URL completa (expandida) para evitar erro de "Página não existe".
    """
    tag = getattr(settings, 'MERCADO_LIVRE_TAG', 'pean3412407')
    # Codifica a URL expandida para o formato web
    clean_url = url.split('?')[0]
    encoded_url = urllib.parse.quote_plus(clean_url)
    return f"https://www.mercadolivre.com.br/social/p/api/p/link-builder/redirect?url={encoded_url}&m_tag={tag}"


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
