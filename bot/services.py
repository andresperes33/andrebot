import re
import time
import os
import hashlib
import json
import urllib.parse
import requests
from django.conf import settings


def _normalizar_url(url):
    """Normaliza uma URL de produto em uma chave estável para deduplicação."""
    url = (url or '').strip().rstrip('.,;|)')
    url = re.split(r'[?#]', url)[0]
    url = re.sub(r'^https?://', '', url, flags=re.I)
    url = re.sub(r'^www\.', '', url, flags=re.I)
    url = url.rstrip('/')
    return url.lower()


def _primeiro_link_produto(texto):
    """Extrai o primeiro link de produto do texto (ignora links de rede social)."""
    for lnk in re.findall(r'(https?://\S+)', texto or ''):
        lnk = lnk.rstrip('.,;|)')
        if any(d in lnk for d in ['t.me/', 'linktr.ee', 'youtube', 'youtu.be', 'tecnan.com.br', 'links.andreindica']):
            continue
        return lnk
    return ''


def _preco_do_texto(texto):
    """Extrai o primeiro preço (R$ ...) do texto, normalizado."""
    preco = ''
    preco_match = re.search(r'R\$\s*[\d.,]+', texto or '')
    if preco_match:
        preco = preco_match.group(0).strip()
    return preco


# Linhas que devem ser ignoradas ao montar o título do produto
_TERMOS_CABECALHO = [
    'postagem original', 'postagem', 'original',
    'canal oficial', 'repostagem', 'repost', 'promo do dia',
    'oferta do dia', 'compra garantida', 'nota fiscal',
    'enviamos para todo brasil', 'produto no brasil', 'produto original',
    'disponivel', 'disponível', 'estoque limitado', 'ultimas unidades',
]
_LOJAS = [
    'aliexpress', 'mercadolivre', 'mercado livre', 'amazon', 'shopee',
    'magalu', 'magazine luiza', 'kabum', 'pichau', 'terabyte', 'americanas',
    'casas bahia', 'extra', 'wish', 'walmart', 'fast shop', 'pontofrio',
    'cnc', 'saraiva', 'submarino', 'lojas rener', 'renner', 'nike', 'adidas',
    'amaro', 'petlove', 'meli', 'farma', 'daki',
]


def _linha_titulo(texto):
    """
    Pega a primeira linha que parece título de produto,
    ignorando cabeçalhos ('Postagem original') e nomes de loja
    que costumam vir ANTES do título real.
    """
    for linha in (texto or '').split('\n'):
        limpa = re.sub(r'[^\w\s.,!?-]', '', linha).strip()
        baixa = limpa.casefold()
        if len(limpa) <= 5:
            continue
        if any(prefixo in baixa for prefixo in _TERMOS_CABECALHO):
            continue
        # Se a linha é só o nome de uma loja (curta e sem pontuacao de produto)
        if any(loja in baixa for loja in _LOJAS) and len(limpa) < 30:
            continue
        return limpa
    return ''


def _chave_dedup(texto):
    """
    Chave de deduplicação estável: link do produto + preço.
    Assim, a MESMA página de produto com preço/cupom diferente
    é tratada como uma NOVA oferta (não é ignorada).
    """
    link = _normalizar_url(_primeiro_link_produto(texto))
    preco = _preco_do_texto(texto)
    if link:
        return f"{link}|{preco}"
    return link


def promo_ja_postada(texto):
    """
    Verifica se uma promoção já foi postada/salva antes.
    Usa uma chave normalizada do PRIMEIRO LINK BRUTO da mensagem,
    que é estável entre restarts (diferente do link convertido/short).
    Retorna True se já existe (deve pular o envio).
    """
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import Promo

    chave = _chave_dedup(texto)
    if not chave:
        return False

    try:
        return Promo.objects.filter(url_chave=chave).exists()
    except Exception as db_err:
        print(f"Erro ao verificar promo existente: {db_err}")
        return False


def save_promo_to_db(texto, photo_path=None, fonte='zFinnY', url_chave=None):
    """
    Salva a promoção no banco de dados para exibição na página web.
    Réplica fiel do texto enviado ao Telegram.
    photo_path pode ser um caminho local ou uma URL de imagem.
    url_chave: chave normalizada do link bruto original (para deduplicação estável).
    """
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import Promo

    if not url_chave:
        url_chave = _chave_dedup(texto)

    # Deduplicação: se a mesma promo (mesma chave) já foi salva antes, ignora.
    if url_chave:
        ja_existe = Promo.objects.filter(url_chave=url_chave).exists()
        if ja_existe:
            print(f"Promo já existente, ignorada: {url_chave}")
            return False

    # Detecta categoria pelo texto
    from bot.classifier import detectar_categoria
    categoria = detectar_categoria(texto)

    # Extrai título básico
    titulo = _linha_titulo(texto)[:250]

    # Brute force link extraction for field legacy
    link_afiliado = ''
    links = re.findall(r'(https?://\S+)', texto)
    if links:
        link_afiliado = links[0].rstrip(')')

    # Preço básico para filtro
    preco = ''
    preco_match = re.search(r'R\$\s*[\d.,]+', texto)
    if preco_match:
        preco = preco_match.group(0).strip()

    # Processa imagem
    imagem_url = ''
    if photo_path and isinstance(photo_path, str) and photo_path.startswith('http'):
        imagem_url = photo_path
    elif photo_path and os.path.exists(photo_path):
        try:
            import shutil
            media_promos_dir = os.path.join(settings.MEDIA_ROOT, 'promos')
            os.makedirs(media_promos_dir, exist_ok=True)
            filename = f"promo_{int(time.time())}_{os.path.basename(photo_path)}"
            new_path = os.path.join(media_promos_dir, filename)
            shutil.copy2(photo_path, new_path)
            imagem_url = f"{settings.MEDIA_URL}promos/{filename}"
        except Exception as img_err:
            print(f"Erro imagem: {img_err}")

    # Deduplicação: se a mesma promo (mesmo link E mesmo preço) já foi salva antes, ignora.
    # Evita promoções duplicadas na página após redeploys/restarts do bot.
    if link_afiliado:
        ja_existe = Promo.objects.filter(link_afiliado=link_afiliado).exists()
        if ja_existe:
            ja_existe_mesmo_preco = Promo.objects.filter(
                link_afiliado=link_afiliado,
                preco=preco,
            ).exists()
            if not ja_existe_mesmo_preco:
                print(f"Promo já salva antes, mas com preço diferente ({preco}): tratando como nova oferta.")
            else:
                print(f"Promo já existente, ignorada: {link_afiliado[:80]}")
                return False

    # Salva
    try:
        promo = Promo.objects.create(
            titulo=titulo or "Oferta imperdível",
            preco=preco,
            cupom='',
            link_afiliado=link_afiliado,
            url_chave=url_chave,
            imagem_url=imagem_url,
            categoria=categoria,
            fonte=fonte,
            texto_original=texto
        )
        print(f"Promo salva: {titulo[:30]} (id={promo.id})")
        return promo.id
    except Exception as db_err:
        print(f"Erro DB: {db_err}")
        return False


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
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        
        # Injeta Cookies se for Mercado Livre
        if 'mercadolivre.com' in url or 'mercadolibre.com' in url:
            ml_cookie = getattr(settings, 'MERCADO_LIVRE_COOKIE', None)
            if ml_cookie:
                headers["Cookie"] = ml_cookie

        try:
            # Se for link curto da Amazon, aproveita para expandir aqui e pegar o nome/imagem real
            if 'amzn.to' in url or 'link.amazon' in url:
                resp_expand = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
                url = resp_expand.url

            # Segue redirecionamentos para chegar na página real do produto
            resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            html = resp.text
            final_url = resp.url

            # Nome via meta tag (og:title ou twitter:title)
            if not name:
                meta_name = re.search(r'<meta[^>]+property=["\'](?:og:title|twitter:title)["\'][^>]+content=["\'](.*?)["\']', html)
                if not meta_name:
                    meta_name = re.search(r'<meta[^>]+name=["\'](?:og:title|twitter:title|title)["\'][^>]+content=["\'](.*?)["\']', html)
                
                if meta_name:
                    name = meta_name.group(1).split('|')[0].strip()
                else:
                    # Fallback para o <title> da página
                    title_match = re.search(r'<title>(.*?)</title>', html)
                    if title_match:
                        name = title_match.group(1).split(':')[0].strip()

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
            elif 'amazon' in final_url or 'link.amazon' in final_url:
                # Tenta várias classes comuns de preço na Amazon
                price_match = re.search(r'class=["\']a-offscreen["\']>(.*?)</span>', html)
                if price_match:
                    price = price_match.group(1).strip()
                else:
                    price_match = re.search(r'class=["\']a-price-whole["\']>(.*?)</span>', html)
                    if price_match:
                        price = f"R$ {price_match.group(1).strip()}"

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
                r'["\']image["\']:["\'](https?://[^"\']+)["\']',
                r'["\']landingImage["\']:["\'](https?://[^"\']+)["\']', # Amazon especifico
                r'id=["\']landingImage["\'][^>]+src=["\'](https?://[^"\']+)["\']', # Amazon seletor
            ]
            
            for pattern in img_patterns:
                img_match = re.search(pattern, html)
                if img_match:
                    found_img = img_match.group(1).strip()
                    # Evita ícones de app ou logos genéricos se possível
                    if 'favicon' in found_img or 'logo' in found_img and image_url:
                        continue
                    image_url = found_img
                    # Limpeza para AliExpress
                    if 'aliexpress' in final_url and '_' in image_url:
                        image_url = image_url.split('_')[0]
                    
                    # Limpeza para Mercado Livre (Alta Resolução)
                    if 'mercadolivre' in final_url and '-O.jpg' in image_url:
                        image_url = image_url.replace('-O.jpg', '-F.jpg')
                    
                    # Limpeza para Amazon (Pegar imagem original sem redimensionamento)
                    if ('amazon' in final_url or 'link.amazon' in final_url) and '._AC_' in image_url:
                        image_url = re.sub(r'\._AC_.*?\.', '.', image_url)
                    
                    # Limpeza para Kabum (Geralmente já vem em boa resolução)
                    if 'kabum.com.br' in final_url and '?' in image_url:
                        image_url = image_url.split('?')[0]
                    
                    if image_url and not any(ext in image_url.lower() for ext in ['.jpg', '.png', '.webp', '.jpeg']):
                        image_url += '.jpg'
                    
                    break # Encontrou uma boa, para.

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
    elif 'amazon.com.br' in url or 'amzn.to' in url or 'link.amazon' in url:
        return convert_amazon_link(url)
    elif 'mercadolivre.com' in url or 'meli.la' in url or 'mlstatic.com' in url or 'mercadolibre.com' in url:
        return convert_mercado_livre_link(url)
    elif 'kabum.com.br' in url or 'tidd.ly' in url:
        return convert_awin_link(url, merchant_id='17729') # Kabum MID padrao
    elif 'magazineluiza.com.br' in url or 'magalu.com' in url or 'mgl.io' in url or 'divulgador.magalu.com' in url:
        return convert_magalu_link(url)
    return None


def convert_mercado_livre_link(url):
    """
    Gera link de afiliado do Mercado Livre.
    1. Expande o link curto (meli.la)
    2. Carrega a página social do ML
    3. Extrai a URL real do produto (MLB) do HTML
    4. Gera link afiliado limpo com nossa tag
    """
    tag = getattr(settings, 'MERCADO_LIVRE_TAG', 'codepysystems')
    matt_tool = getattr(settings, 'MERCADO_LIVRE_MATT_TOOL', '13013217')
    ml_cookie = getattr(settings, 'MERCADO_LIVRE_COOKIE', None)
    
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }
    
    if ml_cookie:
        hdrs["Cookie"] = ml_cookie

    try:
        # 1. Expande o link (meli.la → social/sv...)
        r = requests.get(url, allow_redirects=True, timeout=12, headers=hdrs)
        page_html = r.text

        # 2. Extrai URL do produto real no HTML da página
        import re as _re
        prod_urls = _re.findall(
            r'https://www\.mercadolivre\.com\.br/[^"<>\s]+/p/MLB\d+',
            page_html
        )

        if prod_urls:
            # Pega o primeiro produto e limpa parâmetros extras
            produto_url = prod_urls[0].split('?')[0].split('#')[0]
            affiliate_url = f"{produto_url}?matt_tool={matt_tool}&matt_word={tag}"
            
            # --- Encurtamento meli.la via API Interna ---
            if ml_cookie:
                try:
                    short_api_url = "https://www.mercadolivre.com.br/afiliados/api/v2/partners/social-links"
                    short_hdrs = hdrs.copy()
                    short_hdrs["Content-Type"] = "application/json"
                    short_payload = {"source_url": affiliate_url}
                    
                    short_resp = requests.post(short_api_url, headers=short_hdrs, json=short_payload, timeout=8)
                    if short_resp.status_code == 201 or short_resp.status_code == 200:
                        short_url = short_resp.json().get('short_url')
                        if short_url:
                            print(f"ML Curto (meli.la): {short_url}")
                            return short_url
                except Exception as short_err:
                    print(f"ML Shortener Erro: {short_err}")

            print(f"ML Afiliado (produto): {affiliate_url[:100]}...")
            return affiliate_url

        # Fallback: tenta pegar pelo ID MLB
        mlb_ids = list(set(_re.findall(r'MLB\d+', page_html)))
        if mlb_ids:
            mlb_id = mlb_ids[0]
            affiliate_url = f"https://www.mercadolivre.com.br/p/{mlb_id}?matt_tool={matt_tool}&matt_word={tag}"
            print(f"ML Afiliado (MLB ID): {affiliate_url}")
            return affiliate_url

        print("ML: Nenhum produto encontrado na página.")
        return None

    except Exception as e:
        print(f"ML: Erro na conversão ({e})")
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

    # 4. Fallback: Formato correto confirmado pela API da Awin (awclick.php)
    encoded_url = urllib.parse.quote(url, safe=':/')
    return f"https://www.awin1.com/awclick.php?mid={merchant_id}&id={publisher_id}&ued={encoded_url}"



def convert_magalu_link(url):
    """
    Gera link de afiliado Parceiro Magalu (magazinevoce) de forma infalivel.
    Usa o formato direto de PID que evita erros de slug/404.
    """
    magalu_id = getattr(settings, 'MAGALU_ID', 'magazinein_1546179')
    
    # 1. Expandir links curtos (Magalu mobile/divulgador costuma ser teimoso)
    if any(domain in url for domain in ['mgl.io', 'divulgador.magalu.com', 'magalu.com', 'bit.ly']):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            resp = requests.get(url, allow_redirects=True, timeout=12, headers=headers)
            url = resp.url
        except:
            pass

    # 2. Se ja for magazinevoce, apenas troca o ID
    if 'magazinevoce.com.br' in url:
        return re.sub(r'magazinevoce\.com\.br/[^/]+', f'magazinevoce.com.br/{magalu_id}', url)

    # 3. Extrair o Código do Produto (PID) - O metodo mais seguro
    # Padrao: /p/ID/ ou /produto/ID/
    pid_match = re.search(r'/(?:p|produto)/([a-zA-Z0-9]+)', url)
    
    if pid_match:
        pid = pid_match.group(1)
        # O formato /LOJA/p/ID/ e o que menos da erro 404
        return f"https://www.magazinevoce.com.br/{magalu_id}/p/{pid}/"

    # 4. Caso nao ache o /p/, tenta pegar pelo caminho limpo (Slug)
    match_path = re.search(r'(?:magazineluiza\.com\.br|magalu\.com\.br|magalu\.com)/([^/?]+)', url)
    if match_path:
        slug = match_path.group(1).strip('/')
        if len(slug) > 5:
            return f"https://www.magazinevoce.com.br/{magalu_id}/{slug}/p/produto/"

    # 5. Fallback Final: Link de redirecionamento oficial da Magalu
    # Este link forca o redirecionamento correto com o seu ID
    encoded_url = urllib.parse.quote(url)
    return f"https://www.magazineluiza.com.br/selecao/produtos/?magalu_id={magalu_id}&url={encoded_url}"


def convert_amazon_link(url):
    """
    Gera link de afiliado Amazon injetando a TAG.
    """
    tag = getattr(settings, 'AMAZON_ASSOCIATE_TAG', 'andre0cda-20')
    
    # Se for link curto da Amazon, precisamos expandir para pegar o ID do produto
    if 'amzn.to' in url or 'link.amazon' in url:
        try:
            resp = requests.get(url, allow_redirects=True, timeout=5)
            url = resp.url
        except:
            pass
            
    # Limpa a URL de tags antigas e adiciona a sua
    clean_url = url.split('?')[0]
    return f"{clean_url}?tag={tag}"




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


def convert_aliexpress_link(url, base_on_clean_url=False):
    """API AliExpress"""
    app_key = settings.ALIEXPRESS_APP_KEY
    app_secret = settings.ALIEXPRESS_APP_SECRET
    tracking_id = settings.ALIEXPRESS_TRACKING_ID
    if not app_key or not app_secret: return None

    # Se solicitado (para o link de PC), tentamos pegar a URL real do produto para evitar o fluxo de Moedas do App
    final_url = url
    if base_on_clean_url and ('s.click.aliexpress' in url or 'a.aliexpress.com' in url or 'aliexpress.com/item' not in url):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
            resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            # Pegamos apenas a base da URL antes das interrogações para ser o mais "limpa" possível
            final_url = resp.url.split('?')[0] if '?' in resp.url else resp.url
        except:
            pass

    endpoint = "https://api-sg.aliexpress.com/sync"
    params = {
        "app_key": app_key,
        "format": "json",
        "method": "aliexpress.affiliate.link.generate",
        "sign_method": "md5",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "v": "2.0",
        "promotion_link_type": "0",
        "source_values": final_url,
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


def send_whatsapp_message(text, image_path=None):
    """
    Envia mensagem para o WhatsApp via Evolution API v2.
    Formato correto: JSON com base64 no campo 'media' (sem wrapper 'mediaMessage').
    """
    import os
    import base64

    url_base = getattr(settings, 'EVOLUTION_API_URL', '').strip('/')
    instance = getattr(settings, 'EVOLUTION_API_INSTANCE', '')
    token = getattr(settings, 'EVOLUTION_API_TOKEN', '')
    jid = getattr(settings, 'WHATSAPP_GROUP_JID', '')

    if not all([url_base, instance, token, jid]) or jid == 'seu_jid_do_grupo_aqui@g.us':
        print("WhatsApp: Credenciais ou JID não configurados.")
        return False

    headers = {
        "apikey": token,
        "Content-Type": "application/json"
    }

    try:
        if image_path and os.path.exists(image_path):
            # Evolution Go: envia imagem em base64 no campo 'url' (v0.7.0+)
            endpoint = f"{url_base}/send/media"
            with open(image_path, "rb") as img_file:
                b64 = base64.b64encode(img_file.read()).decode('utf-8')

            payload = {
                "number": jid,
                "caption": text,
                "type": "image",
                "mimetype": "image/jpeg",
                "url": b64
            }
            response = requests.post(endpoint, headers=headers, json=payload, timeout=40)
            print(f"WhatsApp (imagem) Status: {response.status_code} - {response.text[:200]}")

        elif image_path and image_path.startswith('http'):
            # Envio via URL pública
            endpoint = f"{url_base}/send/media"
            payload = {
                "number": jid,
                "caption": text,
                "type": "image",
                "mimetype": "image/jpeg",
                "url": image_path
            }
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            print(f"WhatsApp (url) Status: {response.status_code} - {response.text[:200]}")

        else:
            # Apenas texto
            endpoint = f"{url_base}/send/text"
            payload = {
                "number": jid,
                "text": text
            }
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            print(f"WhatsApp (texto) Status: {response.status_code}")

        return response.status_code in [200, 201]
    except Exception as e:
        print(f"Erro crítico no WhatsApp: {e}")
        return False


def extract_links(text):
    return re.findall(r'(https?://\S+)', text)


def strip_promo_footer(text):
    """
    Remove rodapés promocionais/copys que não devem ser reenviados pelo bot.
    """
    channel_name = getattr(settings, 'PERSONAL_CHANNEL_NAME', 'Seu Canal')
    escaped_channel_name = re.escape(channel_name)

    cleaned_text = re.sub(
        rf'(?im)^\s*{escaped_channel_name}(?:\s+promos?)?\s*$',
        '',
        text,
    )
    cleaned_text = re.sub(r'(?im)^\s*telegram\s*:\s*\S+\s*$', '', cleaned_text)
    cleaned_text = re.sub(r'(?im)^\s*whatsapp\s*:\s*\S+\s*$', '', cleaned_text)
    cleaned_text = re.sub(r'(?im)^\s*#an[uú]ncio\s*$', '', cleaned_text)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    return cleaned_text.strip()


async def process_offer_to_group(bot_app, text, photo=None):
    """
    Processa uma oferta (texto + foto opcional), converte links e posta no grupo.
    bot_app: Instância do bot do Telegram (Bot ou Application)
    """
    if not text:
        return False

    # Filtro: Ignora links da Terabyte
    if 'terabyte' in text.lower() or 'terabyteshop' in text.lower():
        print("ℹ️ Oferta da Terabyte ignorada.")
        return False

    # Detecta se é o Application ou o Bot direto para saber qual objeto usar
    bot = getattr(bot_app, 'bot', bot_app)

    links = extract_links(text)
    if not links:
        return False

    modified_text = text
    original_link = None
    converted_any = False

    # 1. Substituições de Links e Nomes (Canais de terceiros)
    personal_link = getattr(settings, 'PERSONAL_CHANNEL_LINK', '')
    channel_name = getattr(settings, 'PERSONAL_CHANNEL_NAME', 'Seu Canal')
    
    # Limpa nomes de outros canais
    modified_text = re.sub(r'(?i)zFinnY|Iskandar|CaCau|André Indica|Tecnan', channel_name, modified_text)

    # Substitui links do Linktree pelo link personalizado
    modified_text = re.sub(r'https?://linktr\.ee/\S+', 'https://links.andreindica.com.br/', modified_text)
    modified_text = strip_promo_footer(modified_text)

    has_aliexpress = False
    for link in links:
        is_shopee = 'shopee.com.br' in link or 's.shopee' in link
        is_aliexpress = 'aliexpress.com' in link or 's.click.aliexpress' in link
        is_ml = 'mercadolivre.com' in link or 'mlstatic.com' in link or 'mercadolivre.com.br' in link
        is_amazon = 'amazon.com.br' in link or 'amzn.to' in link or 'link.amazon' in link
        is_kabum = 'kabum.com.br' in link or 'tidd.ly' in link
        is_magalu = 'magazineluiza.com.br' in link or 'magalu.com' in link or 'mgl.io' in link
        is_telegram = 't.me/' in link
        is_tecnan = 'tecnan.com.br' in link

        if is_telegram or is_tecnan:
            if personal_link and personal_link not in link:
                modified_text = modified_text.replace(link, personal_link)
                converted_any = True
            continue

        is_awin = 'awin1.com' in link or 'tidd.ly' in link

        if is_awin:
            # Extrai a URL real do produto do parâmetro 'ued' e gera novo link com nosso ID
            extracted_url = None
            if 'ued=' in link:
                try:
                    ued_value = link.split('ued=')[1].split('&')[0]
                    extracted_url = urllib.parse.unquote(ued_value)
                except:
                    pass
            if not extracted_url and 'tidd.ly' in link:
                try:
                    resp = requests.get(link, allow_redirects=True, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                    if 'kabum.com.br' in resp.url:
                        extracted_url = resp.url
                except:
                    pass
            if extracted_url:
                new_awin = convert_awin_link(extracted_url)
                if new_awin:
                    modified_text = modified_text.replace(link, new_awin)
                    original_link = extracted_url
                    converted_any = True
                    continue
            # Fallback: considera como convertido para não bloquear
            converted_any = True
            original_link = link
            continue

        if not any([is_shopee, is_aliexpress, is_ml, is_amazon, is_kabum, is_magalu]):
            continue

        print(f"Convertendo link: {link}")
        converted = convert_to_affiliate_link(link)
        if converted:
            original_link = link
            if is_aliexpress:
                has_aliexpress = True
                link_app = converted
                link_pc = convert_aliexpress_link(link, base_on_clean_url=True)
                # Na primeira ocorrência, substituímos pelo par de links. Nas próximas, apenas por um link simples.
                if "Link para PC:" not in modified_text:
                    replacement = f"🥇 Link com moedas (App):\n🔗 {link_app}\n\n🖥 Link para PC:\n🔗 {link_pc}"
                else:
                    replacement = link_app
            else:
                replacement = converted
            
            modified_text = modified_text.replace(link, replacement)
            converted_any = True

    if not converted_any:
        return False

    # Adiciona as instruções do AliExpress apenas uma vez no final se houver links dele
    if has_aliexpress:
        modified_text += (
            f"\n\n💡 Dica: Comprando pelo aplicativo o desconto pode ser maior por causa das moedas.\n"
            f"Após clicar no link acima, você será direcionado para a página de moedas. Clique no primeiro anúncio.\n"
            f"Se o produto não aparecer, clique em 'DO BRASIL'."
        )

    group_id = settings.TELEGRAM_GROUP_ID
    if not group_id:
        print("Erro: TELEGRAM_GROUP_ID não configurado.")
        return False

    try:
        final_image_to_send = None
        promo_image = None  # Imagem final (path local ou URL) para salvar no site

        if photo:
            # Se 'photo' for um caminho de arquivo (baixado pelo monitor_offers.py)
            # O bot do Telegram envia o arquivo local
            await bot.send_photo(
                chat_id=group_id,
                photo=photo,
                caption=modified_text[:1024]
            )
            final_image_to_send = photo  # Guarda o caminho do arquivo para o WhatsApp

            # Se for um file_id do Telegram (não é path e não é URL), baixa para o disco
            if isinstance(photo, str) and not photo.startswith('http') and not os.path.exists(photo):
                try:
                    tg_file = await bot.get_file(photo)
                    temp_dir = os.path.join(os.getcwd(), 'tmp_photos')
                    os.makedirs(temp_dir, exist_ok=True)
                    promo_image = await tg_file.download_to_drive(custom_path=os.path.join(temp_dir, f"promo_{int(time.time())}.jpg"))
                except Exception as dl_err:
                    print(f"Erro ao baixar foto para o site: {dl_err}")
                    promo_image = None
            else:
                promo_image = final_image_to_send
        else:
            # Tenta buscar info do produto se não tiver foto direto do Telegram
            _, image_url, _ = get_product_info(original_link)
            final_image_to_send = image_url
            promo_image = image_url
            if image_url:
                await bot.send_photo(
                    chat_id=group_id,
                    photo=image_url,
                    caption=modified_text[:1024]
                )
            else:
                await bot.send_message(
                    chat_id=group_id,
                    text=modified_text,
                    disable_web_page_preview=False
                )
        
        # Envia também para o WhatsApp (Passando o arquivo local ou a URL)
        send_whatsapp_message(modified_text, final_image_to_send)

        # Salva a promoção no banco para a página web
        save_promo_to_db(modified_text, promo_image)
        
        return True
    except Exception as e:
        print(f"Erro ao processar oferta automática: {e}")
        return False
