import logging
import os
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v26.0"


def _mensagem_post(texto, pagina_url=''):
    """Monta a mensagem do post: título + preço + link da oferta no site."""
    try:
        from bot.services import _linha_titulo, _preco_do_texto
        titulo = _linha_titulo(texto)[:150]
        preco = _preco_do_texto(texto)
    except Exception:
        titulo = ''
        preco = ''

    mensagem = (titulo or texto or '').strip()
    if not mensagem:
        mensagem = "Oferta imperdível"
    if preco:
        mensagem += f"\n{preco}"
    if pagina_url:
        mensagem += f"\n\n{pagina_url}"
    return mensagem.strip()


def post_facebook(texto, photo_path=None, pagina_url=''):
    """
    Publica a oferta na página do Facebook (Página Nitro Tech).

    Com foto: publica a imagem + mensagem (upload direto).
    Sem foto: publica post de texto + link.
    """
    token = getattr(settings, 'FB_ACCESS_TOKEN', None)
    page_id = getattr(settings, 'FB_PAGE_ID', None)
    if not token or not page_id:
        logger.warning("⚠️ Facebook não configurado (FB_ACCESS_TOKEN / FB_PAGE_ID).")
        return False

    mensagem = _mensagem_post(texto, pagina_url)

    try:
        if photo_path and os.path.exists(photo_path):
            with open(photo_path, 'rb') as foto:
                resp = requests.post(
                    f"{GRAPH_URL}/{page_id}/photos",
                    files={'source': foto},
                    data={'message': mensagem, 'access_token': token},
                    timeout=60,
                )
        else:
            resp = requests.post(
                f"{GRAPH_URL}/{page_id}/feed",
                data={'message': mensagem, 'access_token': token},
                timeout=60,
            )
        data = resp.json()
    except Exception as e:
        logger.error(f"❌ Facebook: erro ao publicar: {e}")
        return False

    if resp.status_code not in (200, 201) or 'id' not in data:
        logger.error(f"❌ Facebook: falha ao publicar: {data}")
        return False

    logger.info(f"✅ Post publicado no Facebook: {data.get('id')}")
    return True


def post_facebook_story(texto, photo_path=None):
    """
    Publica a oferta como STORY na página do Facebook (Photo Stories API).

    Fluxo (docs: developers.facebook.com/docs/page-stories-api):
      1. Upload da foto com published=false (a foto do story NÃO pode ser a
         mesma já usada num post publicado — precisa de cópia própria);
      2. POST /{page_id}/photo_stories com photo_id.

    Requer as mesmas permissões do feed: pages_manage_posts,
    pages_read_engagement, pages_show_list.
    Retorna True se publicado.
    """
    token = getattr(settings, 'FB_ACCESS_TOKEN', None)
    page_id = getattr(settings, 'FB_PAGE_ID', None)
    if not token or not page_id:
        logger.warning("⚠️ Facebook story não configurado (FB_ACCESS_TOKEN / FB_PAGE_ID).")
        return False
    if not photo_path or not os.path.exists(photo_path):
        logger.info("ℹ️ Facebook story: sem foto, pulado.")
        return False

    try:
        # 1) Upload da foto SEM publicar (story precisa de mídia inédita).
        with open(photo_path, 'rb') as foto:
            resp_up = requests.post(
                f"{GRAPH_URL}/{page_id}/photos",
                files={'source': foto},
                data={'published': 'false', 'access_token': token},
                timeout=60,
            )
        up = resp_up.json()
        photo_id = up.get('id')
        if resp_up.status_code not in (200, 201) or not photo_id:
            logger.error(f"❌ Facebook story: falha no upload da foto: {up}")
            return False

        # 2) Publica a foto como story na página.
        resp = requests.post(
            f"{GRAPH_URL}/{page_id}/photo_stories",
            data={'photo_id': photo_id, 'access_token': token},
            timeout=60,
        )
        data = resp.json()
    except Exception as e:
        logger.error(f"❌ Facebook story: erro ao publicar: {e}")
        return False

    if resp.status_code not in (200, 201) or not data.get('success'):
        logger.error(f"❌ Facebook story: falha ao publicar: {data}")
        return False

    logger.info(f"✅ Story publicado no Facebook: post_id={data.get('post_id')}")
    return True