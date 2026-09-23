import re
import os
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.instagram.com/v26.0"


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


def _normalizar_imagem_feed(photo_path):
    """Ajusta a imagem pra proporção aceita pelo feed do IG (4:5 a 1.91:1).

    Se a proporção estiver fora do intervalo, faz crop centralizado.
    Retorna o caminho (possivelmente novo) ou o original se falhar/não precisar.
    """
    if not photo_path or isinstance(photo_path, str) and photo_path.startswith('http'):
        return photo_path
    import os
    if not os.path.exists(photo_path):
        return photo_path
    try:
        from PIL import Image, ImageOps
        with Image.open(photo_path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode in ('RGBA', 'LA', 'P'):
                if img.mode == 'P':
                    img = img.convert('RGBA')
                fundo = Image.new('RGB', img.size, (255, 255, 255))
                fundo.paste(img, mask=img.split()[-1])
                img = fundo
            else:
                img = img.convert('RGB')
            w, h = img.size
            if w <= 0 or h <= 0:
                return photo_path
            ratio = w / h
            min_ratio, max_ratio = 4 / 5, 1.91
            if min_ratio <= ratio <= max_ratio:
                return photo_path
            # Crop central pra caber na faixa válida
            if ratio < min_ratio:
                novo_w = max(1, int(h * min_ratio))
                left = max(0, (w - novo_w) // 2)
                img = img.crop((left, 0, left + novo_w, h))
            else:  # ratio > max_ratio
                nova_h = max(1, int(w / max_ratio))
                top = max(0, (h - nova_h) // 2)
                img = img.crop((0, top, w, top + nova_h))
            base, ext = os.path.splitext(photo_path)
            out = f"{base}_feed{ext or '.jpg'}"
            img.save(out, quality=90)
            logger.info(
                f"✂️ Instagram feed: imagem ajustada p/ proporção "
                f"{img.size[0]}x{img.size[1]} (ratio={img.size[0]/img.size[1]:.3f})"
            )
            return out
    except Exception as e:
        logger.warning(f"⚠️ Instagram feed: não foi possível normalizar imagem: {e}")
        return photo_path


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
            if item:
                logger.warning(f"⚠️ Instagram: item inválido em IG_ACCOUNTS_EXTRA (sem '|'): {item[:40]}…")
            continue
        t, _, uid = item.partition('|')
        t, uid = t.strip(), uid.strip()
        if t and uid:
            contas.append({'token': t, 'user_id': uid})
        else:
            logger.warning("⚠️ Instagram: item vazio em IG_ACCOUNTS_EXTRA (token ou user_id).")
    if not extra and token and user_id:
        logger.warning(
            "⚠️ Instagram: só 1 conta configurada — IG_ACCOUNTS_EXTRA vazio no EasyPanel. "
            "Story/feed NÃO vão para a 2ª conta."
        )
    logger.info(f"📱 Instagram: {len(contas)} conta(s) para publicar: {[c['user_id'] for c in contas]}")
    return contas


def _guardar_link_por_media(media_id, pagina_url, token, ig_user_id):
    """Persiste o link da oferta para um post do feed, para responder 'quero'."""
    import json
    try:
        from django.db import close_old_connections
        from bot.models import BotConfig
        close_old_connections()
        dados = {'url': pagina_url or '', 'token': token, 'user_id': str(ig_user_id)}
        BotConfig.set(f'ig_media_{media_id}', json.dumps(dados))
        if pagina_url:
            BotConfig.set('ig_ultimo_pagina_url', pagina_url)
    except Exception as e:
        logger.error(f"❌ Instagram: erro ao guardar link do media {media_id}: {e}")


def link_por_media(media_id):
    """Recupera o link da oferta de um post do feed (dict url/token/user_id)."""
    import json
    try:
        from django.db import close_old_connections
        from bot.models import BotConfig
        close_old_connections()
        valor = BotConfig.get(f'ig_media_{media_id}', '')
        if valor:
            return json.loads(valor)
    except Exception as e:
        logger.warning(f"⚠️ Instagram: erro ao ler link do media {media_id}: {e}")
    return None


def _erro_cota_esgotada(dados):
    """True se o erro do Instagram for o limite de publicação de mídia (subcode 2207042)."""
    if not isinstance(dados, dict):
        return False
    err = dados.get('error') or {}
    return err.get('code') == 9 and err.get('error_subcode') == 2207042


def _cota_insta_disponivel(token, ig_user_id):
    """Checa a cota de publicação de conteúdo do Instagram (janela móvel de 24h).

    Retorna (disponivel: bool, uso: int, total: int). Em caso de falha na
    consulta, assume que a cota está disponível (não bloqueia a publicação).
    """
    try:
        from django.db import close_old_connections
        close_old_connections()
        resp = requests.get(
            f"{GRAPH_URL}/{ig_user_id}/content_publishing_limit",
            params={"fields": "config", "access_token": token},
            timeout=30,
        )
        data = resp.json()
        lista = data.get('data') or []
        if lista and lista[0].get('config'):
            cfg = lista[0]['config']
            uso = int(cfg.get('quota_usage', 0) or 0)
            total = int(cfg.get('quota_total', 0) or 0)
            return uso < total, uso, total
    except Exception as e:
        logger.warning(f"⚠️ Instagram: erro ao ler cota de publicação ({ig_user_id}): {e}")
    return True, 0, 0


def _postar_conta(token, ig_user_id, imagem_url, caption, pagina_url, media_type='STORIES'):
    """Publica um container (Story ou Feed) em UMA conta. Retorna media_id ou False."""
    payload = {
        "image_url": imagem_url,
        "media_type": media_type,
        "caption": caption,
        "access_token": token,
    }
    if media_type == 'STORIES' and pagina_url:
        payload["link_url"] = pagina_url
        logger.info(f"🔗 Instagram Story (conta {ig_user_id}): link_url={pagina_url}")
    elif media_type == 'STORIES':
        logger.warning(f"⚠️ Instagram Story (conta {ig_user_id}): pagina_url vazio — sem sticker de link.")
    # Feed (IMAGE/REELS): link vai na legenda; não existe link_url — não é erro.

    # Consulta a cota de publicação de 24h ANTES de criar o container. Se estiver
    # esgotada, não queima chamadas tentando publicar (erro 9 / subcode 2207042).
    disponivel, uso, total = _cota_insta_disponivel(token, ig_user_id)
    if not disponivel:
        logger.warning(f"⏸️ Instagram: cota de publicação esgotada na conta {ig_user_id} ({uso}/{total}) — pulando.")
        return False

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
        if _erro_cota_esgotada(data):
            logger.warning(f"⏸️ Instagram: cota de publicação esgotada na conta {ig_user_id} — pulando.")
        else:
            logger.error(f"❌ Instagram: falha ao criar media (resposta completa): {data}")
        return False

    logger.info(f"✅ Instagram: container criado (conta={ig_user_id}, id={data.get('id')}, link_url={'link_url' in payload})")

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
        if _erro_cota_esgotada(pub_data):
            logger.warning(f"⏸️ Instagram: cota de publicação esgotada na conta {ig_user_id} — pulando.")
        else:
            logger.error(f"❌ Instagram: falha ao publicar: {pub_data}")
        return False

    rotulo = 'Story' if media_type == 'STORIES' else 'Post no feed'
    logger.info(f"✅ {rotulo} publicado no Instagram! (conta={ig_user_id}, media={pub_data['id']})")
    return pub_data['id']


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
    # foto + texto completo da promoção + link do produto no rodapé.
    if photo_path and not (isinstance(photo_path, str) and photo_path.startswith('http')):
        try:
            from bot.story_composer import compor_story_card
            from bot.services import texto_card
            mensagem = texto_card(texto) or titulo
            story_path = compor_story_card(photo_path, mensagem, pagina_url=pagina_url)
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
            logger.info(f"📤 Instagram Story: publicando na conta {conta['user_id']}…")
            media_id = _postar_conta(conta['token'], conta['user_id'], imagem_url, caption, pagina_url)
            if media_id:
                publicou = True
                # Mapa story → oferta: quem responder o Story recebe o link na DM.
                _guardar_link_por_media(media_id, pagina_url, conta['token'], conta['user_id'])
            else:
                logger.error(f"❌ Instagram Story: falhou na conta {conta['user_id']}.")
        except Exception as e:
            logger.error(f"❌ Instagram: erro na conta {conta['user_id']}: {e}")
    if not publicou:
        logger.error("❌ Instagram Story: nenhuma conta publicou.")
    return publicou


def post_instagram_feed(texto, photo_path=None, pagina_url=''):
    """
    Publica a oferta no FEED do Instagram (publicação normal do perfil) em
    TODAS as contas configuradas. Usa a foto original (sem card de Story) e o
    link da página do produto vai na legenda, já que feed não tem link clicável.
    """
    contas = _contas_instagram()
    if not contas:
        logger.warning("⚠️ Instagram não configurado (IG_ACCESS_TOKEN / IG_USER_ID).")
        return False

    titulo, preco, link = _titulo_preco_link(texto)

    # Feed exige proporção 4:5 .. 1.91:1 — normaliza antes de enviar.
    photo_path = _normalizar_imagem_feed(photo_path)
    imagem_url = _url_publica_imagem(photo_path)
    if not imagem_url:
        logger.warning("⚠️ Instagram feed: nenhuma imagem disponível.")
        return False

    caption = titulo or "Promoção imperdível"
    if preco:
        caption += f" — {preco}"
    # Legenda sem o link (gatilho): quem quiser o link comenta/avisa "EU QUERO"
    # e o bot envia o link na DM. O mapa media→link é salvo no banco na publicação.
    caption += "\n\nQuer aproveitar a promoção? Digite EU QUERO que te mando o link! 🔗"

    publicou = False
    for conta in contas:
        try:
            logger.info(f"📤 Instagram feed: publicando na conta {conta['user_id']}…")
            media_id = _postar_conta(conta['token'], conta['user_id'], imagem_url, caption, pagina_url, media_type='IMAGE')
            if media_id:
                publicou = True
                # Guarda o link da oferta no banco: quando alguém comentar
                # "quero" ou mandar DM, o bot sabe qual link responder.
                _guardar_link_por_media(media_id, pagina_url, conta['token'], conta['user_id'])
            else:
                logger.error(f"❌ Instagram feed: falhou na conta {conta['user_id']}.")
        except Exception as e:
            logger.error(f"❌ Instagram feed: erro na conta {conta['user_id']}: {e}")
    if not publicou:
        logger.error("❌ Instagram feed: nenhuma conta publicou.")
    return publicou
