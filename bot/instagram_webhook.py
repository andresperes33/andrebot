"""
Webhook do Instagram: recebe eventos de comentários e mensagens diretas e
automatiza a resposta "quero" — respondendo o comentário (avisando que o link
foi enviado na DM) e/ou enviando o link via DM quando o usuário msg o bot.

Endpoints usados:
- Responder comentário: POST /v19.0/{ig-comment-id}/replies
- Enviar DM:           POST graph.facebook.com/v19.0/{ig-user-id}/messages
"""
import json
import logging
import re
import time
import unicodedata

import requests
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.instagram.com/v26.0"

# Evita responder 2x o mesmo comentário/mensagem (webhooks reentregam eventos)
_processadas = {}


def _norm(texto):
    """Minúsculas sem acentos, para casar com 'quero'."""
    texto = (texto or '').lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def _ja_processada(chave, janela_seg=300):
    agora = time.time()
    visto = _processadas.get(chave, 0)
    if agora - visto < janela_seg:
        return True
    _processadas[chave] = agora
    return False


def _link_da_oferta(media_id=None):
    """Busca o link. Prioriza o media do post; senão, o último postado."""
    from bot.instagram_stories import link_por_media
    dados = link_por_media(media_id) if media_id else None
    if dados and dados.get('url'):
        return dados['url'], dados.get('token'), dados.get('user_id')
    try:
        from django.db import close_old_connections
        from bot.models import BotConfig
        close_old_connections()
        ultimo = BotConfig.get('ig_ultimo_pagina_url', '')
        return (ultimo, None, None) if ultimo else ('', None, None)
    except Exception:
        return ('', None, None)


def _responder_comentario(token, comment_id, texto):
    try:
        resp = requests.post(
            f"{GRAPH_URL}/{comment_id}/replies",
            data={"message": texto, "access_token": token},
            timeout=30,
        )
        dados = resp.json()
    except Exception as e:
        logger.error(f"❌ IG webhook: erro ao responder comentário {comment_id}: {e}")
        return False
    if resp.status_code != 200 or 'id' not in dados:
        logger.error(f"❌ IG webhook: falha ao responder comentário: {dados}")
        return False
    logger.info(f"✅ IG webhook: comentário {comment_id} respondido (reply={dados['id']}).")
    return True


def _enviar_dm(token, ig_user_id, recipient_id, texto, comment_id=None):
    """
    Envia uma DM. Se comment_id for passado, usa o mecanismo de Private Reply
    do Instagram: inicia uma DM a partir de um comentário no post
    (recipient = {"comment_id": ...}). Sem comment_id, responde numa conversa
    já existente (recipient = {"id": ...}).
    """
    if comment_id:
        recipient = {"comment_id": str(comment_id)}
    else:
        recipient = {"id": str(recipient_id)}
    try:
        resp = requests.post(
            f"{GRAPH_URL}/{ig_user_id}/messages",
            data={
                "recipient": json.dumps(recipient),
                "message": json.dumps({"text": texto}),
                "access_token": token,
            },
            timeout=30,
        )
        dados = resp.json()
    except Exception as e:
        logger.error(f"❌ IG webhook: erro ao enviar DM: {e}")
        return False
    if resp.status_code != 200 or 'error' in dados:
        logger.error(f"❌ IG webhook: falha ao enviar DM: {dados}")
        return False
    logger.info(f"✅ IG webhook: DM enviado para {recipient_id} (comment_id={comment_id or '-'}).")
    return True


def _texto_resposta(link, modo):
    link = (link or '').strip()
    if link:
        return f"✅ Aproveite a promoção!\n\n🔗 {link}"
    site = (getattr(settings, 'SITE_URL', '') or 'https://www.nitrotech.store').rstrip('/')
    return f"✅ Promo confirmada! Confira no nosso site:\n{site}"


def _link_da_caption(media_id, token):
    """Lê a legenda do post no Instagram e extrai o link do produto (a página
    do produto do site já é postada na legenda do feed)."""
    try:
        resp = requests.get(
            f"{GRAPH_URL}/{media_id}",
            params={"fields": "caption", "access_token": token},
            timeout=30,
        )
        dados = resp.json()
    except Exception as e:
        logger.warning(f"⚠️ IG webhook: erro ao ler legenda do media {media_id}: {e}")
        return ''
    caption = (dados.get('caption') or '')
    links = re.findall(r'(https?://\S+)', caption)
    if not links:
        return ''
    return links[0].rstrip('.,;|)')


def _processar_comentario(value):
    """Comentário no feed: tenta mandar o link na DM do comentador; se o
    Instagram recusar (nem toda conta libera), responde no próprio comentário."""
    comment_id = value.get('id')
    text = value.get('text') or ''
    media_id = value.get('media_id')
    sender_id = (value.get('from') or {}).get('id')

    # Reply que nós mesmos postamos → ignora (evita loop)
    if value.get('parent_id') or not comment_id:
        return

    if 'quero' not in _norm(text):
        return

    if _ja_processada(f'comentario:{comment_id}'):
        return

    link, token, user_id = _link_da_oferta(media_id)
    if not token:
        from bot.instagram_stories import _contas_instagram
        contas = _contas_instagram()
        if not contas:
            logger.warning("⚠️ IG webhook: Instagram não configurado para responder.")
            return
        token = contas[0]['token']
    if not user_id:
        from bot.instagram_stories import _contas_instagram
        contas = _contas_instagram()
        user_id = contas[0]['user_id'] if contas else ''

    # Link da DM: prioriza o mapa do post; se não houver (post antigo), lê a
    # legenda do post, onde fica o link da página do produto.
    dm_link = link
    if not dm_link and media_id and token:
        dm_link = _link_da_caption(media_id, token)
    dm_link = dm_link or link

    # 1ª tentativa: Private Reply — inicia a DM a partir do comentário
    # (recipient.comment_id). É a forma oficial de mandar DM pra quem comentou.
    if token and user_id:
        dm_enviado = False
        try:
            dm_enviado = _enviar_dm(token, user_id, sender_id, _texto_resposta(dm_link, 'dm'), comment_id=comment_id)
        except Exception as e:
            logger.error(f"❌ IG webhook: erro no Private Reply: {e}")

        if dm_enviado:
            # Avisa no comentário que o link foi para a DM (agora é verdade)
            _responder_comentario(token, comment_id, "✅ Prontinho! Te mandei o link na sua DM 📩")
            return

    # 2ª tentativa (fallback): responder o comentário com o link
    _responder_comentario(token, comment_id, _texto_resposta(link, 'comentario'))


def _processar_mensagem(value, entry_id):
    """DM com 'quero': envia o link direto na conversa."""
    sender = (value.get('from') or {}).get('id')
    msg = value.get('message') or {}
    text = (msg.get('text') or '') if isinstance(msg, dict) else str(msg)
    mid = (msg.get('mid') or '') if isinstance(msg, dict) else ''

    if not sender or not text:
        return

    if 'quero' not in _norm(text):
        return

    if _ja_processada(f'dm:{mid or sender}'):
        return

    link, token, user_id = _link_da_oferta()
    if not user_id:
        user_id = entry_id
    if not token:
        from bot.instagram_stories import _contas_instagram
        contas = _contas_instagram()
        if not contas:
            logger.warning("⚠️ IG webhook: Instagram não configurado para enviar DM.")
            return
        token = contas[0]['token']

    _enviar_dm(token, user_id, sender, _texto_resposta(link, 'dm'))


def processar_evento_instagram(payload):
    try:
        entries = payload.get('entry') or []
    except AttributeError:
        logger.warning("⚠️ IG webhook: payload inesperado: %r", payload)
        return

    contadas = 0
    for entry in entries:
        entry_id = entry.get('id', '')
        for change in entry.get('changes') or []:
            field = change.get('field')
            value = change.get('value') or {}
            if field in ('comments', 'comments_edge', 'caption') and value:
                _processar_comentario(value)
                contadas += 1
            elif field in ('messages', 'messaging') and value:
                _processar_mensagem(value, entry_id)
                contadas += 1
    if contadas:
        logger.info(f"IG webhook: {contadas} eventos processados.")


@csrf_exempt
def instagram_webhook_view(request):
    """View do webhook: GET = validação (handshake), POST = eventos."""
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        expected = getattr(settings, 'IG_WEBHOOK_VERIFY_TOKEN', '')
        if mode == 'subscribe' and token and expected and token == expected:
            return HttpResponse(challenge)
        return HttpResponse('Verification failed', status=403)

    if request.method == 'POST':
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception as e:
            logger.error(f"❌ IG webhook: JSON inválido: {e}")
            return JsonResponse({'status': 'error'}, status=400)

        if payload.get('object') == 'instagram':
            processar_evento_instagram(payload)
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=405)