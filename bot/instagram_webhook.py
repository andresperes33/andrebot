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
    """Minúsculas sem acentos, para casar com os gatilhos."""
    texto = (texto or '').lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


_GATILHOS_INTERESSE = (
    'quero', 'eu quero', 'link', 'manda', 'onde', 'qual o link', 'preco',
    'comprar', 'valor', 'envia', 'passa o link', 'cade o link', 'mandar'
)


def _tem_interesse(texto):
    """Verifica se o comentário ou mensagem indica interesse no produto/link."""
    t = _norm(texto)
    if not t:
        return False
    return any(gatilho in t for gatilho in _GATILHOS_INTERESSE)


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
    site = (getattr(settings, 'SITE_URL', '') or 'https://promos.andreindicatech.com.br').rstrip('/')
    return f"✅ Promo confirmada! Confira no nosso site:\n{site}"


def _link_da_caption(media_id, token):
    """Lê o post no Instagram (via Graph API) e busca a promoção correspondente.
    1. Se a legenda tiver um link direto, retorna o link.
    2. Se a legenda não tiver link (caso do Feed com 'EU QUERO'), busca no
       banco de dados a Promo correspondente com base no título da legenda."""
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
    if links:
        return links[0].rstrip('.,;|)')

    # Se não há link na legenda, busca a Promo no banco que bata com a primeira linha (título)
    primeira_linha = caption.split('\n')[0].strip()
    if primeira_linha:
        # Remove sufixo de preço se houver (ex: 'Título — R$ 199')
        titulo_busca = primeira_linha.split(' — ')[0].strip()[:80]
        if titulo_busca:
            try:
                from django.db import close_old_connections
                from bot.models import Promo
                close_old_connections()
                promo = Promo.objects.filter(titulo__icontains=titulo_busca).order_by('-id').first()
                if promo:
                    base_site = (getattr(settings, 'SITE_URL', '') or 'https://promos.andreindicatech.com.br').rstrip('/')
                    url_encontrada = f"{base_site}/promos/{promo.pk}/"
                    logger.info(f"✅ IG webhook: Promo #{promo.pk} encontrada no banco a partir da legenda ('{titulo_busca}').")
                    return url_encontrada
            except Exception as e:
                logger.warning(f"⚠️ IG webhook: erro ao buscar Promo por legenda: {e}")

    return ''


def _processar_comentario(value):
    """Comentário no feed: tenta mandar o link na DM do comentador; se o
    Instagram recusar (nem toda conta libera), responde no próprio comentário."""
    comment_id = value.get('id')
    text = value.get('text') or ''
    # No webhook do Instagram, o media_id pode vir em value['media_id'] ou value['media']['id']
    media_id = value.get('media_id')
    if not media_id and isinstance(value.get('media'), dict):
        media_id = value.get('media', {}).get('id')
    sender_id = (value.get('from') or {}).get('id')

    # Reply que nós mesmos postamos → ignora (evita loop)
    if value.get('parent_id') or not comment_id:
        logger.info(f"🔍 IG webhook: comentário ignorado (parent={value.get('parent_id')}, id={comment_id}).")
        return

    if not _tem_interesse(text):
        logger.info(f"🔍 IG webhook: comentário sem palavra de interesse (text={text[:40]!r}).")
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

    # Link da DM: prioriza o mapa do post; se não houver (post antigo ou não mapeado),
    # lê a legenda do post (caption), onde fica o link da página do produto.
    dm_link = link
    origem = 'mapa' if dm_link else '?'
    if not dm_link and media_id and token:
        dm_link = _link_da_caption(media_id, token)
        origem = 'legenda' if dm_link else 'legenda-vazia'
    dm_link = dm_link or link
    if not dm_link:
        origem = 'site'
    logger.info(f"🔍 IG webhook: media={media_id} link_origem={origem} url={dm_link}")

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
    _responder_comentario(token, comment_id, _texto_resposta(dm_link, 'comentario'))


def _processar_mensagem(value, entry_id):
    """DM com 'quero': envia o link direto na conversa.

    Se a mensagem for uma RESPOSTA a um Story (replies_to.story/shares),
    prioriza o link da oferta daquele Story postado por nós; senão usa o
    último link postado.

    Suporta os dois formatos de payload do Meta:
    - value.messaging[0] (messenger antigo)
    - value.sender/recipient/message (formato direto dos webhooks do IG)."""
    from bot.instagram_stories import link_por_media

    sender = ''
    mid = ''
    text = ''
    story_id = ''

    messaging = value.get('messaging') or []
    if messaging:
        m = messaging[0]
        sender = (m.get('sender') or {}).get('id') or ''
        msg = m.get('message') or {}
    else:
        # Formato direto: sender/recipient/message vêm direto no value
        sender = (value.get('sender') or {}).get('id') or (value.get('from') or {}).get('id') or ''
        msg = value.get('message') or {}

    if isinstance(msg, dict):
        mid = (msg.get('mid') or '').strip()
        text = (msg.get('text') or '').strip()
        # Resposta a Story → replies_to.story
        replies_to = msg.get('replies_to')
        if isinstance(replies_to, dict):
            story = replies_to.get('story') or {}
            if isinstance(story, dict):
                story_id = (story.get('id') or '').strip()
        if not story_id:
            # Outro formato: shares com type='story'
            shares = msg.get('shares') or []
            if isinstance(shares, list):
                for s in shares:
                    if isinstance(s, dict) and s.get('type') == 'story':
                        story_id = (s.get('id') or '').strip()
                        break
    else:
        text = str(msg or '').strip()

    if not sender or not text:
        return

    if 'quero' not in _norm(text):
        logger.info(f"🔍 IG webhook: mensagem sem 'quero' (sender={sender}, texto={text[:40]!r}).")
    if not _tem_interesse(text):
        logger.info(f"🔍 IG webhook: mensagem sem palavra de interesse (sender={sender}, texto={text[:40]!r}).")
        return

    if _ja_processada(f'dm:{mid or (sender + ":" + story_id)}'):
        return

    # Link e credenciais padrão (último postado / conta principal)
    link, token, user_id = _link_da_oferta()
    origem = 'ultimo' if link else '?'

    # Resposta a Story → usa o mapa daquele Story (fixa qual conta/qual oferta)
    if story_id:
        dados = link_por_media(story_id)
        if dados:
            link = dados.get('url') or link
            token = dados.get('token') or token
            user_id = dados.get('user_id') or user_id
            origem = 'story-mapa' if dados.get('url') else 'story-mapa-vazio'
        logger.info(f"🔍 IG webhook: resposta a Story={story_id} origem={origem}")

    if not user_id:
        user_id = entry_id
    if not token:
        from bot.instagram_stories import _contas_instagram
        contas = _contas_instagram()
        if not contas:
            logger.warning("⚠️ IG webhook: Instagram não configurado para enviar DM.")
            return
        token = contas[0]['token']
        user_id = user_id or contas[0]['user_id']

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
        logger.info(f"🔔 IG webhook: GET de verificação recebido (mode={request.GET.get('hub.mode')}).")
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

        logger.info(f"🔔 IG webhook: POST recebido (object={payload.get('object')}), entries={len(payload.get('entry') or [])}")
        if payload.get('object') == 'instagram':
            processar_evento_instagram(payload)
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=405)