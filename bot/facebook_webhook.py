"""
Webhook do Facebook (Messenger): recebe mensagens de quem responde um Story
ou manda DM para a Página e automatiza o resposta com o link da promoção.

Fluxo no Meta app (produto Messenger → Webhooks):
  URL de callback:  {SITE_URL}/facebook/webhook/
  Verificar token:  FB_WEBHOOK_VERIFY_TOKEN (env)
  Campo assinado:   messages (da Página)

Envio da resposta: POST graph.facebook.com/v26.0/me/messages (Send API)
com o FB_ACCESS_TOKEN da Página (permissão pages_messaging).
"""
import json
import logging
import time

import requests
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from bot.instagram_webhook import (
    _tem_interesse,
    _texto_resposta,
    _ja_processada,
    _INTRO_DM,
    _imagem_da_promo,
)

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v26.0"


def _link_da_oferta():
    """Link da última oferta publicada no Facebook (salvo no post/story)."""
    try:
        from django.db import close_old_connections
        from bot.models import BotConfig
        close_old_connections()
        ultimo = BotConfig.get('fb_ultimo_pagina_url', '')
        if ultimo:
            return ultimo
    except Exception:
        pass
    return (getattr(settings, 'SITE_URL', '') or '').rstrip('/') + '/promos/'


def _post_mensagem(psid, message_dict, token):
    resp = requests.post(
        f"{GRAPH_URL}/me/messages",
        data={
            'recipient': json.dumps({'id': str(psid)}),
            'message': json.dumps(message_dict),
            'messaging_type': 'RESPONSE',
            'access_token': token,
        },
        timeout=30,
    )
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {'raw': resp.text[:300]}


def _enviar_dm(psid, texto, link=''):
    """Envia a DM do Facebook em 2 passos: intro + card/texto com o link."""
    token = getattr(settings, 'FB_ACCESS_TOKEN', None)
    if not token:
        logger.warning("⚠️ FB webhook: FB_ACCESS_TOKEN ausente.")
        return False
    try:
        # 1) Intro (mesmo texto do Instagram)
        st, dt = _post_mensagem(psid, {'text': _INTRO_DM}, token)
        if st != 200 or 'error' in dt:
            logger.warning(f"⚠️ FB webhook: intro não enviada: {dt}")
        else:
            logger.info("💬 FB webhook: intro enviada antes do link.")

        # 2) Card com imagem+botão se houver promo; senão, texto com link
        imagem, _path, titulo = _imagem_da_promo(link) if link else ('', '', '')
        if imagem and link:
            element = {
                'title': (titulo or 'Aproveite a promoção!')[:80],
                'subtitle': 'Toque para ver a oferta',
                'image_url': imagem,
                'default_action': {'type': 'web_url', 'url': link},
                'buttons': [{'type': 'web_url', 'url': link, 'title': 'Ver oferta'}],
            }
            st, dt = _post_mensagem(psid, {
                'attachment': {
                    'type': 'template',
                    'payload': {
                        'template_type': 'generic',
                        'elements': [element],
                    },
                },
            }, token)
            if st == 200 and 'error' not in dt:
                logger.info(f"✅ FB webhook: card enviado para {psid}.")
                return True
            logger.warning(f"⚠️ FB webhook: template falhou, mandando texto: {dt}")

        st, dt = _post_mensagem(psid, {'text': texto}, token)
    except Exception as e:
        logger.error(f"❌ FB webhook: erro ao enviar DM: {e}")
        return False
    if st != 200 or 'error' in dt:
        logger.error(f"❌ FB webhook: falha ao enviar DM: {dt}")
        return False
    logger.info(f"✅ FB webhook: DM enviado para {psid}.")
    return True


def _processar_mensagem(item, page_id=''):
    """Mensagem recebida da Página (DM ou resposta a Story)."""
    if item.get('delivery') or item.get('read'):
        return
    sender = (item.get('sender') or {}).get('id') or ''
    msg = item.get('message') or {}
    if not sender or not isinstance(msg, dict):
        return
    if msg.get('is_echo'):
        return
    # Não responde a própria Página
    if page_id and str(sender) == str(page_id):
        return

    text = (msg.get('text') or '').strip()
    mid = msg.get('mid') or ''

    # Resposta a Story do Facebook: costuma vir em message.reply_to / shares.
    # Se for resposta a story, o envio é automático (já demonstrou interesse);
    # senão, exige palavra de interesse (quero, link, etc.).
    eh_resposta_story = bool(
        msg.get('reply_to')
        or msg.get('shares')
        or (item.get('message') or {}).get('referral')
        or item.get('referral')
    )

    if not eh_resposta_story and not _tem_interesse(text):
        logger.info(f"🔍 FB webhook: mensagem sem interesse (sender={sender}, texto={text[:40]!r}).")
        return

    if _ja_processada(f'fb:{mid or sender}'):
        return

    link = _link_da_oferta()
    _enviar_dm(sender, _texto_resposta(link, 'dm'), link=link)


def processar_evento_facebook(payload):
    if payload.get('object') != 'page':
        return
    for entry in payload.get('entry') or []:
        page_id = str(entry.get('id') or '')
        # Só processa a nossa Página (evita cross-talk se outro webhook apontar aqui)
        fb_page = str(getattr(settings, 'FB_PAGE_ID', '') or '')
        if fb_page and page_id and page_id != fb_page:
            logger.info(f"🔍 FB webhook: entry de outra página ({page_id}), ignorando.")
            continue
        for item in entry.get('messaging') or []:
            if item:
                try:
                    _processar_mensagem(item, page_id)
                except Exception as e:
                    logger.error(f"❌ FB webhook: erro ao processar mensagem: {e}")


@csrf_exempt
def facebook_webhook_view(request):
    """View do webhook: GET = validação (handshake), POST = eventos."""
    if request.method == 'GET':
        logger.info(f"🔔 FB webhook: GET de verificação (mode={request.GET.get('hub.mode')}).")
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        expected = getattr(settings, 'FB_WEBHOOK_VERIFY_TOKEN', '')
        if mode == 'subscribe' and token and expected and token == expected:
            return HttpResponse(challenge)
        return HttpResponse('Verification failed', status=403)

    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception as e:
            logger.error(f"❌ FB webhook: JSON inválido: {e}")
            return JsonResponse({'status': 'error'}, status=400)
        logger.info(f"🔔 FB webhook: POST recebido (object={payload.get('object')}).")
        try:
            processar_evento_facebook(payload)
        except Exception as e:
            logger.error(f"❌ FB webhook: erro ao processar evento: {e}")
        # Sempre 200 — o Meta reentrega se a resposta demorar/falhar
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=405)
