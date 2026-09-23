import logging
import os
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_URL = "https://api.twitter.com/2/tweets"
UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
# No X, toda URL conta como 23 caracteres no limite de 280
_URL_LEN = 23


def _auth():
    ck = getattr(settings, 'TWITTER_CONSUMER_KEY', '')
    cks = getattr(settings, 'TWITTER_CONSUMER_SECRET', '')
    at = getattr(settings, 'TWITTER_ACCESS_TOKEN', '')
    ats = getattr(settings, 'TWITTER_ACCESS_TOKEN_SECRET', '')
    if not (ck and cks and at and ats):
        return None
    from requests_oauthlib import OAuth1
    return OAuth1(ck, client_secret=cks, resource_owner_key=at, resource_owner_secret=ats)


def _len_x(msg):
    """Tamanho efetivo da mensagem no X (URLs contam como 23 chars)."""
    total = len(msg)
    for u in re.findall(r'https?://\S+', msg or ''):
        total += _URL_LEN - len(u.rstrip('.,;)'))
    return total


def _mensagem(texto, pagina_url=''):
    """Monta o tweet: título + preço + link da oferta no site."""
    try:
        from bot.services import _linha_titulo, _preco_do_texto
        titulo = _linha_titulo(texto)[:150]
        preco = _preco_do_texto(texto)
    except Exception:
        titulo = ''
        preco = ''

    msg = (titulo or texto or '').strip()
    if not msg:
        msg = "Oferta imperdível"
    if preco:
        msg += f"\n{preco}"
    if pagina_url:
        msg += f"\n\n{pagina_url}"
    return msg.strip()


def _cortar(msg, max_len=280):
    """Corta o corpo da mensagem preservando o link final, se precisar."""
    if _len_x(msg) <= max_len:
        return msg
    partes = msg.rsplit('\n\n', 1)
    if len(partes) == 2 and partes[1].startswith('http'):
        link = partes[1]
        corpo = partes[0]
        while corpo and _len_x(corpo + '\n\n' + link) > max_len:
            corpo = corpo[:-1].rstrip()
        return f"{corpo}\n\n{link}" if corpo else link
    return msg[:max_len]


def _upload_media(photo_path, auth):
    """Sobe a foto (media/upload v1.1) e retorna media_id ou None."""
    try:
        with open(photo_path, 'rb') as f:
            resp = requests.post(UPLOAD_URL, files={'media': f}, auth=auth, timeout=60)
        data = resp.json()
    except Exception as e:
        logger.warning(f"⚠️ X: erro no upload da mídia: {e}")
        return None
    mid = data.get('media_id_string')
    if resp.status_code not in (200, 201) or not mid:
        logger.warning(f"⚠️ X: upload da mídia falhou: {data}")
        return None
    return mid


def post_twitter(texto, photo_path=None, pagina_url=''):
    """
    Publica a oferta no X (Twitter) via API v2 (POST /2/tweets).
    OAuth 1.0a (Consumer Key/Secret + Access Token/Secret).
    Com foto: sobe a mídia e anexa; sem foto: só o texto.
    Retorna True se publicado.
    """
    auth = _auth()
    if not auth:
        logger.warning("⚠️ X/Twitter não configurado (TWITTER_*).")
        return False

    msg = _cortar(_mensagem(texto, pagina_url))

    media_id = None
    if photo_path and os.path.exists(photo_path):
        media_id = _upload_media(photo_path, auth)

    payload = {'text': msg}
    if media_id:
        payload['media'] = {'media_ids': [media_id]}

    try:
        resp = requests.post(API_URL, json=payload, auth=auth, timeout=30)
        data = resp.json()
    except Exception as e:
        logger.error(f"❌ X: erro ao publicar: {e}")
        return False

    if resp.status_code not in (200, 201) or not (data.get('data') or {}).get('id'):
        logger.error(f"❌ X: falha ao publicar: {data}")
        return False

    logger.info(f"✅ Tweet publicado: {data['data']['id']}")
    return True
