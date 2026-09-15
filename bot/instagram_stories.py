import re
import os
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.instagram.com/v19.0"


def _titulo_preco_link(texto):
    """Extrai título, preço e primeiro link de um texto de promoção."""
    try:
        from bot.services import _linha_titulo, _preco_do_texto
        titulo = _linha_titulo(texto)[:120]
        preco = _preco_do_texto(texto)
    except Exception:
        titulo = ''
        for linha in (texto or '').split('\n'):
            limpa = re.sub(r'[^\w\s.,!?-]', '', linha).strip()
            if len(limpa) > 5:
                titulo = limpa[:120]
                break
        preco = ''
        preco_match = re.search(r'R\$\s*[\d.,]+', texto or '')
        if preco_match:
            preco = preco_match.group(0).strip()

    link = ''
    links = re.findall(r'(https?://\S+)', texto or '')
    if links:
        link = links[0].rstrip('.,;|)')

    return titulo, preco, link


def _url_publica_imagem(photo_path):
    """
    Converte uma imagem local em URL pública acessível pelo Instagram.
    Copia para MEDIA_ROOT/promos/ e monta a URL a partir do SITE_URL.
    """
    if not photo_path:
        return ''

    if isinstance(photo_path, str) and photo_path.startswith('http'):
        return photo_path

    import os
    import time
    import shutil
    base_url = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
    if not base_url or not os.path.exists(photo_path):
        return ''

    media_promos_dir = os.path.join(settings.MEDIA_ROOT, 'promos')
    os.makedirs(media_promos_dir, exist_ok=True)
    filename = f"ig_{int(time.time())}_{os.path.basename(photo_path)}"
    new_path = os.path.join(media_promos_dir, filename)
    shutil.copy2(photo_path, new_path)
    return f"{base_url}{settings.MEDIA_URL}promos/{filename}"


def _contas_instagram():
    """Lista todas as contas de Instagram configuradas.

    Cada conta é um dict {'token': ..., 'user_id': ...}. A conta principal vem
    de IG_ACCESS_TOKEN/IG_USER_ID; contas extras de IG_ACCOUNTS_EXTRA
    (formato 'token|user_id,token2|user_id2')."""
    contas = []
    token = getattr(settings, 'IG_ACCESS_TOKEN', None)
    user_id = getattr(settings, 'IG_USER_ID', None)
    if token and user_id:
        contas.append({'token': token, 'user_id': str(user_id)})
    extra = getattr(settings, 'IG_ACCOUNTS_EXTRA', '') or ''
    for item in extra.split(','):
        item = item.strip()
        if not item or '|' not in item:
            continue
        t, _, uid = item.partition('|')
        t, uid = t.strip(), uid.strip()
        if t and uid:
            contas.append({'token': t, 'user_id': uid})
    return contas


def _postar_conta(token, ig_user_id, imagem_url, caption, pagina_url):
    """Publica um Story em UMA conta específica. Retorna True/False."""
    payload = {
        "image_url": imagem_url,
        "media_type": "STORIES",
        "caption": caption,
        "access_token": token,
    }
    if pagina_url:
        payload["link_url"] = pagina_url

    try:
        resp = requests.post(
            f"{GRAPH_URL}/{ig_user_id}/media",
            data=payload,
            timeout=30,
        )
        data = resp.json()
    except Exception as e:
        logger.error(f"❌ Instagram: erro ao criar container: {e}")
        return False

    if resp.status_code != 200 or 'id' not in data:
        logger.error(f"❌ Instagram: falha ao criar media: {data}")
        return False

    creation_id = data['id']

    # 2. Aguarda a mídia ficar pronta (o Instagram precisa processar a imagem)
    import time as _time
    for _tentativa in range(6):
        _time.sleep(5)
        try:
            status = requests.get(
                f"{GRAPH_URL}/{creation_id}",
                params={"fields": "status_code", "access_token": token},
                timeout=30,
            )
            sc = status.json()
        except Exception:
            continue
        if sc.get('status_code') in ('FINISHED', 'PUBLISHED'):
            break

    # 3. Publica o container
    try:
        pub = requests.post(
            f"{GRAPH_URL}/{ig_user_id}/media_publish",
            data={
                "creation_id": creation_id,
                "access_token": token,
            },
            timeout=30,
        )
        pub_data = pub.json()
    except Exception as e:
        logger.error(f"❌ Instagram: erro ao publicar: {e}")
        return False

    if pub.status_code != 200 or 'id' not in pub_data:
        logger.error(f"❌ Instagram: falha ao publicar: {pub_data}")
        return False

    logger.info(f"✅ Story publicado no Instagram! (media={pub_data['id']})")
    return True


def post_instagram_story(texto, photo_path=None, pagina_url=''):
    """
    Publica um Story no Instagram em TODAS as contas configuradas.
    Usa a Instagram Graph API (media + media_publish).
    pagina_url: URL da página do produto no site (adiciona sticker de link clicável).
    """
    contas = _contas_instagram()
    if not contas:
        logger.warning("⚠️ Instagram não configurado (IG_ACCESS_TOKEN / IG_USER_ID).")
        return False

    titulo, preco, link = _titulo_preco_link(texto)

    # Se houver foto local, compõe o Story no estilo do card do site:
    # foto + texto completo da promoção + faixa "LINK NA BIO".
    if photo_path and not (isinstance(photo_path, str) and photo_path.startswith('http')):
        try:
            from bot.story_composer import compor_story_card
            from bot.services import texto_card
            mensagem = texto_card(texto) or titulo
            story_path = compor_story_card(photo_path, mensagem)
            if story_path and os.path.exists(story_path):
                photo_path = story_path
        except Exception as e:
            logger.error(f"⚠️ Instagram: erro ao compor Story: {e}")

    imagem_url = _url_publica_imagem(photo_path)

    if not imagem_url:
        logger.warning("⚠️ Instagram: nenhuma imagem disponível para o Story.")
        return False

    # Monta a legenda do Story
    caption = titulo or "Promoção imperdível"
    if preco:
        caption += f" — {preco}"
    if link:
        caption += f"\n\n{link}"

    publicou = False
    for conta in contas:
        try:
            if _postar_conta(conta['token'], conta['user_id'], imagem_url, caption, pagina_url):
                publicou = True
        except Exception as e:
            logger.error(f"❌ Instagram: erro na conta {conta['user_id']}: {e}")
    return publicou
