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
import os
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

# entry_id do webhook ≠ IG user id da API. Cache entry → user_id real
# (aprendido quando um evento bate no mapa media→conta).
_entry_user_cache = {}


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


def _enviar_dm(token, ig_user_id, recipient_id, texto, comment_id=None, imagem_url=None, imagem_path=None, titulo=''):
    """
    Envia UMA mensagem na DM.

    - Com imagem: Generic Template (imagem + título + botão do link juntos).
    - Sem imagem (ou template falhar): texto puro.

    Private Reply (comment_id) aceita só UMA mensagem — nunca manda 2.
    """
    if comment_id:
        recipient = {"comment_id": str(comment_id)}
    else:
        recipient = {"id": str(recipient_id)}

    def _post_msg(msg_dict):
        resp = requests.post(
            f"{GRAPH_URL}/{ig_user_id}/messages",
            data={
                "recipient": json.dumps(recipient),
                "message": json.dumps(msg_dict),
                "access_token": token,
            },
            timeout=30,
        )
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, {"raw": resp.text[:300]}

    def _link_no_texto(t):
        m = re.search(r'(https?://\S+)', t or '')
        return m.group(1).rstrip('.,;|)') if m else ''

    try:
        link = _link_no_texto(texto)
        titulo = (titulo or '').strip()[:80] or 'Aproveite a promoção!'
        subtitle = 'Toque para ver a oferta' if link else (texto or '')[:80]

        # 1) Card único: imagem + título + botão do link
        if imagem_url:
            element = {
                "title": titulo,
                "subtitle": subtitle,
                "image_url": imagem_url,
            }
            if link:
                element["default_action"] = {"type": "web_url", "url": link}
                element["buttons"] = [{"type": "web_url", "url": link, "title": "Ver oferta"}]
            status, dados = _post_msg({
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "generic",
                        "elements": [element],
                    },
                }
            })
            if status == 200 and 'error' not in dados:
                logger.info(f"✅ IG webhook: card (imagem+link) enviado na DM.")
                logger.info(f"✅ IG webhook: DM enviado para {recipient_id} (comment_id={comment_id or '-'}).")
                return True
            logger.warning(f"⚠️ IG webhook: template falhou, tentando texto puro: {dados}")

        # 2) Texto puro (só UMA chamada — private reply não aceita 2)
        status, dados = _post_msg({"text": texto})
    except Exception as e:
        logger.error(f"❌ IG webhook: erro ao enviar DM: {e}")
        return False
    if status != 200 or 'error' in dados:
        logger.error(f"❌ IG webhook: falha ao enviar DM: {dados}")
        return False
    logger.info(f"✅ IG webhook: DM enviado para {recipient_id} (comment_id={comment_id or '-'}).")
    return True


def _imagem_da_promo(pagina_url):
    """Extrai /promos/<pk>/ e retorna (url_jpeg, caminho_local, titulo_preco).

    titulo_preco: "Produto — R$ 99" (corta em 80 p/ o card do IG).
    """
    if not pagina_url:
        return '', '', ''
    m = re.search(r'/promos/(\d+)', pagina_url)
    if not m:
        return '', '', ''
    try:
        from django.db import close_old_connections
        from bot.models import Promo
        close_old_connections()
        promo = Promo.objects.filter(pk=int(m.group(1))).first()
        if not promo or not promo.imagem_url:
            return '', '', ''
        titulo_card = (promo.titulo or '').strip()
        if promo.preco:
            titulo_card = f"{titulo_card} — {promo.preco}".strip()
        titulo_card = titulo_card[:80] or 'Aproveite a promoção!'
        img = promo.imagem_url
        site = (getattr(settings, 'SITE_URL', '') or 'https://promos.andreindicatech.com.br').rstrip('/')
        abs_url = img if img.startswith('http') else f"{site}{img}"

        # Se já é jpg/jpeg/png, resolve path local se existir
        lower = abs_url.lower().split('?')[0]
        if lower.endswith(('.jpg', '.jpeg', '.png')):
            local = ''
            if abs_url.startswith(site):
                rel = abs_url[len(site):].lstrip('/')
                cand = os.path.join(settings.BASE_DIR, rel)
                if os.path.isfile(cand):
                    local = cand
            return abs_url, local, titulo_card

        # WebP (ou outro): baixa e converte pra JPEG local
        url, path = _webp_para_jpeg_url(abs_url, promo.pk)
        return url, path, titulo_card
    except Exception as e:
        logger.warning(f"⚠️ IG webhook: erro ao buscar imagem da promo: {e}")
        return '', '', ''


def _webp_para_jpeg_url(abs_url, promo_pk):
    """Baixa a imagem, converte pra JPEG se preciso e retorna (url, path)."""
    import time
    import tempfile
    from PIL import Image

    site = (getattr(settings, 'SITE_URL', '') or 'https://promos.andreindicatech.com.br').rstrip('/')
    media_dir = os.path.join(settings.MEDIA_ROOT, 'promos')
    os.makedirs(media_dir, exist_ok=True)
    out_name = f"ig_dm_{promo_pk}_{int(time.time())}.jpg"
    out_path = os.path.join(media_dir, out_name)

    # Tenta usar o arquivo local se a URL for do próprio site (evita download)
    local_src = None
    if abs_url.startswith(site):
        rel = abs_url[len(site):].lstrip('/')
        cand = os.path.join(settings.BASE_DIR, rel)
        if os.path.exists(cand):
            local_src = cand

    try:
        if local_src:
            img = Image.open(local_src)
        else:
            resp = requests.get(abs_url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.img') as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name
            img = Image.open(tmp_path)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        img.load()  # força decodificação (WebP lazy)
        if img.mode in ('RGBA', 'LA', 'P'):
            if img.mode == 'P':
                img = img.convert('RGBA')
            fundo = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                fundo.paste(img, mask=img.split()[-1])
            else:
                fundo.paste(img)
            img = fundo
        else:
            img = img.convert('RGB')
        # Limite de lado (IG prefere <= 8192)
        max_side = 2048
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side), Image.LANCZOS)
        img.save(out_path, 'JPEG', quality=90)
        url = f"{site}{settings.MEDIA_URL}promos/{out_name}"
        logger.info(f"🖼️ IG webhook: imagem convertida p/ JPEG → {url}")
        return url, out_path
    except Exception as e:
        logger.warning(f"⚠️ IG webhook: falha ao converter imagem p/ JPEG: {e}")
        return abs_url, ''


def _texto_resposta(link, modo):
    link = (link or '').strip()
    if modo == 'dm':
        if link:
            return f"✅ Aproveite a promoção!\n\n🔗 {link}"
        site = (getattr(settings, 'SITE_URL', '') or 'https://promos.andreindicatech.com.br').rstrip('/')
        return f"✅ Promo confirmada! Confira no nosso site:\n{site}"
    # comentário no post: só avisa que o link foi pra DM (não repete a promo)
    return "📩 Link do produto enviado na sua DM!"


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


def _processar_comentario(value, entry_id=None):
    """Comentário no feed: tenta mandar o link na DM do comentador; se o
    Instagram recusar (nem toda conta libera), responde no próprio comentário."""
    comment_id = value.get('id')
    text = value.get('text') or ''
    # No webhook do Instagram, o media_id pode vir em value['media_id'] ou value['media']['id']
    media_id = value.get('media_id')
    if not media_id and isinstance(value.get('media'), dict):
        media_id = value.get('media', {}).get('id')
    sender_id = (value.get('from') or {}).get('id')

    logger.info(
        f"📩 IG webhook: comentário entry_id={entry_id} media={media_id} "
        f"sender={sender_id} text={text[:40]!r}"
    )

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
    origem_mapa = bool(token and user_id)
    if not token or not user_id:
        from bot.instagram_stories import _contas_instagram
        contas = _contas_instagram()
        if not contas:
            logger.warning("⚠️ IG webhook: Instagram não configurado para responder.")
            return
        # entry_id do webhook costuma ser diferente do IG user id da API —
        # tenta entry, cache e recipient-like ids antes de desistir.
        cached = _entry_user_cache.get(str(entry_id)) if entry_id else None
        conta_match = _acha_conta(contas, entry_id, cached) or contas[0]
        token = token or conta_match['token']
        user_id = user_id or conta_match['user_id']
        logger.info(
            f"🔍 IG webhook: mapa ausente — fallback entry={entry_id} cache={cached} → "
            f"conta user_id={conta_match.get('user_id')} "
            f"(match={str(conta_match.get('user_id'))==str(entry_id)})"
        )
    if entry_id and user_id:
        _entry_user_cache[str(entry_id)] = str(user_id)
    logger.info(
        f"🔍 IG webhook: media={media_id} origem_mapa={origem_mapa} "
        f"conta_user_id={user_id} token_prefix={(token or '')[:12]}…"
    )

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

    # 1ª tentativa: Private Reply — UMA msg com imagem+link (ou texto).
    if token and user_id:
        dm_enviado = False
        imagem, imagem_path, titulo = _imagem_da_promo(dm_link)
        try:
            dm_enviado = _enviar_dm(
                token, user_id, sender_id, _texto_resposta(dm_link, 'dm'),
                comment_id=comment_id, imagem_url=imagem, imagem_path=imagem_path,
                titulo=titulo,
            )
        except Exception as e:
            logger.error(f"❌ IG webhook: erro no Private Reply: {e}")

        if dm_enviado:
            _responder_comentario(token, comment_id, "✅ Prontinho! Te mandei o link na sua DM 📩")
            return

    # 2ª tentativa (fallback): só avisa no comentário (sem expor o link)
    _responder_comentario(token, comment_id, "📩 Link do produto enviado na sua DM!")


def _acha_conta(contas, *ids):
    """Acha a conta configurada cujo user_id bate com algum dos ids passados."""
    for cid in ids:
        if not cid:
            continue
        for c in contas:
            if str(c.get('user_id')) == str(cid):
                return c
    return None


def _resolver_conta_dm(entry_id, recipient_id, token_mapa=None, user_id_mapa=None):
    """Resolve (token, user_id) da conta certa pra enviar DM.

    Prioridade:
    1. Dados do mapa media/story (já vêm com token+user_id da conta certa)
    2. recipient.id / entry_id casando com contas configuradas
    3. Cache entry_id → user_id aprendido em eventos anteriores
    """
    from bot.instagram_stories import _contas_instagram
    contas = _contas_instagram()
    if not contas:
        logger.warning("⚠️ IG webhook: Instagram não configurado para enviar DM.")
        return None, None

    if token_mapa and user_id_mapa:
        return token_mapa, user_id_mapa

    conta = _acha_conta(contas, recipient_id, entry_id)
    if not conta and entry_id:
        cached = _entry_user_cache.get(str(entry_id))
        conta = _acha_conta(contas, cached)
    if not conta and recipient_id:
        cached = _entry_user_cache.get(str(recipient_id))
        conta = _acha_conta(contas, cached)

    if conta:
        logger.info(
            f"🔍 IG webhook: conta resolvida user_id={conta['user_id']} "
            f"(recipient={recipient_id} entry={entry_id} "
            f"match_recipient={str(conta.get('user_id'))==str(recipient_id)} "
            f"match_entry={str(conta.get('user_id'))==str(entry_id)})"
        )
        return conta['token'], conta['user_id']

    logger.warning(
        f"⚠️ IG webhook: não achou conta p/ DM "
        f"(entry={entry_id} recipient={recipient_id} contas={[c.get('user_id') for c in contas]})"
    )
    return None, None


def _processar_mensagem(value, entry_id):
    """DM com 'quero': envia o link direto na conversa.

    Se a mensagem for uma RESPOSTA a um Story (reply_to.story),
    prioriza o link da oferta daquele Story postado por nós; senão usa o
    último link postado.

    Suporta os dois formatos de payload do Meta:
    - value.messaging[0] (messenger antigo)
    - value.sender/recipient/message (formato direto dos webhooks do IG)."""
    from bot.instagram_stories import link_por_media

    sender = ''
    recipient = ''
    mid = ''
    text = ''
    story_id = ''

    messaging = value.get('messaging') or []
    if messaging and isinstance(messaging, list):
        m = messaging[0]
        sender = (m.get('sender') or {}).get('id') or ''
        recipient = (m.get('recipient') or {}).get('id') or ''
        msg = m.get('message') or {}
    else:
        # Formato direto: sender/recipient/message vêm direto no item do webhook
        sender = (value.get('sender') or {}).get('id') or (value.get('from') or {}).get('id') or ''
        recipient = (value.get('recipient') or {}).get('id') or ''
        msg = value.get('message') or {}

    if isinstance(msg, dict):
        mid = (msg.get('mid') or '').strip()
        text = (msg.get('text') or '').strip()
        # Resposta a Story → Meta usa reply_to (sem "s"); legado: replies_to
        reply_to = msg.get('reply_to') or msg.get('replies_to')
        if isinstance(reply_to, dict):
            story = reply_to.get('story') or {}
            if isinstance(story, dict):
                story_id = (story.get('id') or '').strip()
        if not story_id:
            # shares com type='story'
            shares = msg.get('shares') or []
            if isinstance(shares, list):
                for s in shares:
                    if isinstance(s, dict) and s.get('type') in ('story', 'ig_story'):
                        story_id = (s.get('id') or '').strip()
                        break
        if not story_id:
            # attachments com type story/ig_story
            for att in msg.get('attachments') or []:
                if isinstance(att, dict) and att.get('type') in ('story', 'ig_story'):
                    payload = att.get('payload') or {}
                    story_id = (payload.get('id') or payload.get('url') or '').strip()
                    if story_id:
                        break
    else:
        text = str(msg or '').strip()

    if not sender:
        return

    logger.info(
        f"📩 IG webhook: mensagem entry={entry_id} recipient={recipient or '-'} "
        f"sender={sender} story_id={story_id or '-'} mid={mid or '-'} text={text[:40]!r}"
    )

    # Se a pessoa respondeu diretamente a um Story, ela já está querendo o link daquele Story!
    # Caso seja uma DM normal, precisa conter uma das palavras de interesse (quero, link, etc.)
    if not story_id and not _tem_interesse(text):
        logger.info(f"🔍 IG webhook: mensagem sem palavra de interesse (sender={sender}, texto={text[:40]!r}).")
        return

    if _ja_processada(f'dm:{mid or (sender + ":" + story_id)}'):
        return

    # Link padrão (último postado)
    link, _t_mapa, _u_mapa = _link_da_oferta()
    origem = 'ultimo' if link else '?'
    token_mapa = None
    user_id_mapa = None

    # Resposta a Story → usa o mapa daquele Story (fixa qual conta/qual oferta)
    if story_id:
        dados = link_por_media(story_id)
        if dados:
            link = dados.get('url') or link
            token_mapa = dados.get('token')
            user_id_mapa = dados.get('user_id')
            origem = 'story-mapa' if dados.get('url') else 'story-mapa-vazio'
        else:
            origem = 'story-sem-mapa'
        logger.info(f"🔍 IG webhook: resposta a Story={story_id} origem={origem}")

    token, user_id = _resolver_conta_dm(
        entry_id, recipient,
        token_mapa=token_mapa, user_id_mapa=user_id_mapa,
    )
    if not token or not user_id:
        # Sem conta resolvível — não tenta mandar com ID errado
        return

    # Aprende entry_id/recipient → user_id real pra próximos eventos sem mapa
    if user_id:
        if entry_id:
            _entry_user_cache[str(entry_id)] = str(user_id)
        if recipient:
            _entry_user_cache[str(recipient)] = str(user_id)

    imagem, imagem_path, titulo = _imagem_da_promo(link)
    logger.info(
        f"📤 IG webhook: enviando DM conta_user_id={user_id} "
        f"token_prefix={(token or '')[:12]}… origem={origem} imagem={'sim' if imagem else 'não'}"
    )
    ok = _enviar_dm(
        token, user_id, sender, _texto_resposta(link, 'dm'),
        imagem_url=imagem, imagem_path=imagem_path, titulo=titulo,
    )
    if not ok:
        logger.error(
            f"❌ IG webhook: FALHOU enviar DM para conta_user_id={user_id} "
            f"sender={sender} entry={entry_id} recipient={recipient} origem={origem}"
        )


def processar_evento_instagram(payload):
    try:
        entries = payload.get('entry') or []
    except AttributeError:
        logger.warning("⚠️ IG webhook: payload inesperado: %r", payload)
        return

    contadas = 0
    for entry in entries:
        entry_id = entry.get('id', '')

        # 1. Formato padrão do Messenger/Instagram Messaging: entry['messaging'] = [ {...} ]
        # É EXATAMENTE onde chegam as DMs e respostas a Stories!
        for msg_item in entry.get('messaging') or []:
            if msg_item:
                _processar_mensagem(msg_item, entry_id)
                contadas += 1

        # 2. Formato por mudanças: entry['changes'] = [ {'field': ..., 'value': ...} ]
        for change in entry.get('changes') or []:
            field = change.get('field')
            value = change.get('value') or {}
            if field in ('comments', 'comments_edge', 'caption') and value:
                _processar_comentario(value, entry_id)
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

        obj = payload.get('object')
        entries = payload.get('entry') or []
        entry_ids = [e.get('id') for e in entries if isinstance(e, dict)]
        logger.info(
            f"🔔 IG webhook: POST recebido (object={obj}), "
            f"entries={len(entries)} entry_ids={entry_ids}"
        )
        if obj in ('instagram', 'page'):
            processar_evento_instagram(payload)
        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=405)