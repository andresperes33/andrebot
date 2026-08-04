import re
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.instagram.com/v19.0"


def _titulo_preco_link(texto):
    """Extrai título, preço e primeiro link de um texto de promoção."""
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


def post_instagram_story(texto, photo_path=None):
    """
    Publica um Story no Instagram com a imagem, título, preço e link da oferta.
    Usa a Instagram Graph API (media + media_publish).
    """
    token = getattr(settings, 'IG_ACCESS_TOKEN', None)
    ig_user_id = getattr(settings, 'IG_USER_ID', None)

    if not token or not ig_user_id:
        logger.warning("⚠️ Instagram não configurado (IG_ACCESS_TOKEN / IG_USER_ID).")
        return False

    titulo, preco, link = _titulo_preco_link(texto)
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

    # 1. Cria o container de mídia (STORIES)
    try:
        resp = requests.post(
            f"{GRAPH_URL}/{ig_user_id}/media",
            data={
                "image_url": imagem_url,
                "media_type": "STORIES",
                "caption": caption,
                "access_token": token,
            },
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

    # 2. Publica o container
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
