import asyncio
import logging
import os
import re
import time
import unicodedata
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from bot.models import Promo
from bot.services import AVISO_CUPOM
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from asgiref.sync import sync_to_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Aviso anexado a toda promoção enviada ao Telegram (canal fonte) — segue
# junto para todos os outros canais (WhatsApp, site, alertas).
_AVISO_PROMOCAO = "⏳A promoção pode encerrar a qualquer momento."

# Aviso que permanece no TG/Zap (o de rodapé de canais sai)
_AVISO_AUTOMATICO = (
    "⚠️ Aviso: as ofertas são geradas automaticamente e podem conter erros. "
    "Confirme preço e disponibilidade na loja antes de comprar."
)

# Dica de persuasão sobre comprar pelo app da loja (vai acima do aviso no TG)
_AVISO_APP_LOJA = (
    "📲 Comprando pelo app da loja o valor final pode sair MAIS BARATO! "
    "Muitas lojas liberam cupons, moedas e descontos exclusivos só no "
    "aplicativo. Vale conferir antes de finalizar a compra."
)


# Categorias que NÃO vão para o Instagram/Facebook (feed/stories)
_CATS_BLOQUEADAS_REDES = {'cupom', 'filtro_linha', 'outros', 'cabo', 'pasta_termica', 'caixa_som'}


def _texto_sem_rodape(texto):
    """Remove o aviso de promoção — ele fica só no site, não no TG/Zap."""
    return (texto or '').replace(f"\n\n{_AVISO_PROMOCAO}", '').strip()


def _remover_divulgacao_grupo_impulso(texto):
    """Remove convites de grupo e links do jogo de Impulso, preservando a oferta."""
    remover_linha = (
        'grupo de impulso no whatsapp',
        'seuhardware.com/s/kkdmpdl',
        'chat.whatsapp.com',
        'whatsapp.com/channel',
    )
    linhas = []
    for linha in (texto or '').splitlines():
        baixa = linha.casefold()
        if any(marcador in baixa for marcador in remover_linha):
            continue
        if 'joguinho de impulso' in baixa:
            # Mantém o texto, mas remove qualquer link relacionado a ele.
            linha = re.sub(r'https?://\S+', '', linha).rstrip()
        linhas.append(linha)
    return '\n'.join(linhas)


def _eh_link_grupo(url):
    """Detecta links que levam para grupos/canais de WhatsApp ou Telegram."""
    u = (url or '').casefold()
    return (
        'chat.whatsapp.com' in u
        or 'whatsapp.com/channel' in u
        or 't.me/' in u
        or 'telegram.me/' in u
    )


def _normalizar_nome_canal(nome):
    """Normaliza nome/@username para comparação tolerante a acentos/emoji.

    Ex.: 'Promoções Gamer' casa com 'Promocoes Gamer' e com
    'Promoções Gamer 🔥' (o usuário pode configurar com ou sem acento).
    """
    nome = (nome or '').strip().lstrip('@').casefold()
    nome = unicodedata.normalize('NFKD', nome)
    nome = ''.join(c for c in nome if not unicodedata.combining(c))
    nome = re.sub(r'\s+', ' ', nome).strip()
    return nome


def _links_relevantes_para_dedup(urls):
    """Remove links que não são de produto (grupos, redes, assinaturas)."""
    ignorar = (
        't.me/', 'telegram.me/', 'linktr.ee', 'youtube', 'youtu.be',
        'tecnan.com.br', 'links.andreindica', 'chat.whatsapp.com',
        'whatsapp.com/channel',
    )
    vistos = set()
    resultado = []
    for url in urls:
        url = (url or '').strip().rstrip('.,;|)')
        if not url or _eh_link_grupo(url):
            continue
        if any(marcador in url.casefold() for marcador in ignorar):
            continue
        if url not in vistos:
            vistos.add(url)
            resultado.append(url)
    return resultado


def _expandir_urls_para_dedup(urls):
    """Expande links curtos quando ainda não há uma chave específica.

    Ex.: um link `s.shopee.com.br/abc` não revela o ID do produto. Seguindo
    o redirecionamento, ele vira `shopee.com.br/product/...`, permitindo
    reconhecer a mesma oferta postada por outro canal.
    """
    from bot.services import _chave_link_produto, _expandir_link_curto

    extras = []
    for url in urls:
        chave = _chave_link_produto(url)
        if chave and ':' in chave:
            # Já identifica o produto (ex.: 'shopee:111:222'); não precisa
            # de requisição de rede.
            continue
        expandida = _expandir_link_curto(url)
        if expandida and expandida != url:
            extras.append(expandida)
    if not extras:
        return urls
    return _links_relevantes_para_dedup(urls + extras)

# ─── Cache em memória para last_processed_id ─────────────────────────────────
# Evita chamadas constantes ao banco em contexto async — mais seguro e rápido.
# Na inicialização, carrega do banco (persiste entre deploys).
# A cada save, atualiza a memória E persiste no banco.
# O last_id é POR CANAL: cada canal monitorado tem o seu próprio (os IDs de
# mensagens são relativos a cada canal).
_last_ids: dict = {}
_last_ids_loaded: dict = {}
_processing_ids: set = set()
# Lock por canal: mensagens do MESMO canal são processadas em série. Sem isso,
# 3 ofertas simultâneas disputam conversão de link e o last_id avança por uma
# enquanto outra falha — a que falhou nunca era reprocessada.
_channel_locks: dict = {}
# Tentativas por mensagem: se falhar sempre, libera a fila após N tentativas.
_falhas_processamento: dict = {}
_MAX_TENTATIVAS_PROCESSAMENTO = 3


def _chave_last_id(nome_canal):
    """Chave estável para guardar o last_id de cada canal no BotConfig."""
    return f"last_processed_id_{nome_canal.strip().casefold()}"


@sync_to_async
def _db_get_last_id(chave):
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import BotConfig
    return BotConfig.get(chave, '0')

@sync_to_async
def _db_set_last_id(chave, msg_id):
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import BotConfig
    BotConfig.set(chave, msg_id)

@sync_to_async
def _db_get_channel():
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import BotConfig
    return BotConfig.get('monitored_channel', '')

@sync_to_async
def _db_set_channel(channel):
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import BotConfig
    BotConfig.set('monitored_channel', channel)

async def load_last_id(nome_canal: str) -> int:
    chave = _chave_last_id(nome_canal)
    if _last_ids_loaded.get(chave):
        return _last_ids.get(chave, 0)
    try:
        val = await _db_get_last_id(chave)
        _last_ids[chave] = int(val)
        logger.info(f"📌 Último ID carregado do banco ({nome_canal}): {_last_ids[chave]}")
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível carregar last_id ({nome_canal}): {e}. Usando 0.")
        _last_ids[chave] = 0
    _last_ids_loaded[chave] = True
    return _last_ids[chave]

async def save_last_id(nome_canal: str, msg_id: int, forcar: bool = False):
    chave = _chave_last_id(nome_canal)
    atual = _last_ids.get(chave, 0)
    # Nunca retrocede: com mensagens concorrentes, uma mais antiga terminando
    # depois não pode sobrescrever o last_id de uma mais nova.
    if not forcar and msg_id <= atual:
        return
    _last_ids[chave] = msg_id
    try:
        await _db_set_last_id(chave, msg_id)
    except Exception as e:
        logger.error(f"❌ Erro ao persistir last_id={msg_id} ({nome_canal}) no banco: {e}")


def _lock_do_canal(nome_canal: str):
    """Retorna o lock que serializa o processamento de um canal."""
    lock = _channel_locks.get(nome_canal)
    if lock is None:
        lock = asyncio.Lock()
        _channel_locks[nome_canal] = lock
    return lock


async def _converter_link_com_retry(link, tentativas: int = 2):
    """Converte o link FORA do event loop (requests é síncrono) e tenta de novo.

    Sem o to_thread, uma conversão lenta bloqueia todo o monitor e pode fazer
    as outras ofertas serem canceladas/perdidas.
    """
    from bot.services import convert_to_affiliate_link

    for tentativa in range(1, tentativas + 1):
        try:
            convertido = await asyncio.to_thread(convert_to_affiliate_link, link)
            if convertido:
                return convertido
        except Exception as e:
            logger.warning(
                f"⚠️ Falha ao converter link (tentativa {tentativa}/{tentativas}): {e}"
            )
        if tentativa < tentativas:
            await asyncio.sleep(1)
    logger.warning(f"⚠️ Não foi possível converter o link: {link[:120]}")
    return None





class Command(BaseCommand):
    help = 'Monitor do canal de promoções -> Telegram + WhatsApp (Autônomo, PC pode estar desligado)'

    def handle(self, *args, **options):
        api_id = getattr(settings, 'TELEGRAM_API_ID', None)
        api_hash = getattr(settings, 'TELEGRAM_API_HASH', None)
        group_id = int(getattr(settings, 'TELEGRAM_GROUP_ID', 0))

        async def main():
            string_session = getattr(settings, 'TELEGRAM_STRING_SESSION', None)
            if string_session:
                logger.info("📡 Iniciando sessão via StringSession...")
                client = TelegramClient(StringSession(string_session), api_id, api_hash, connection_retries=None)
            else:
                logger.info("📂 Iniciando sessão via arquivo local...")
                client = TelegramClient('session_monitor', api_id, api_hash, connection_retries=None)
            
            await client.start()

            # ─── Canais monitorados ─────────────────────────────────────────
            # Canal principal (SOURCE_CHANNEL_USERNAME) + canais extras
            # (EXTRA_SOURCE_CHANNELS). Cada canal pode ter um filtro:
            #   filtro=None        → captura todas as ofertas
            #   filtro='aliexpress'→ captura SÓ ofertas com link AliExpress
            canais = []
            canal_principal = getattr(settings, 'SOURCE_CHANNEL_USERNAME', 'zFinnY').strip()
            if canal_principal:
                canais.append({'nome': canal_principal, 'filtro': None})
            for extra in (getattr(settings, 'EXTRA_SOURCE_CHANNELS', []) or []):
                nome_extra = (extra.get('nome') or '').strip()
                if nome_extra:
                    canais.append({'nome': nome_extra, 'filtro': extra.get('filtro') or None})

            # Resolve o ID de cada canal e faz o cold start individual
            for canal in canais:
                canal_nome = canal['nome']
                canal_norm = _normalizar_nome_canal(canal_nome)
                canal_sem_espaco = canal_norm.replace(' ', '')
                logger.info(f"🔍 Localizando ID do canal {canal_nome}...")
                target_id = None
                async for dialog in client.iter_dialogs():
                    dialog_name = _normalizar_nome_canal(dialog.name)
                    dialog_username = _normalizar_nome_canal(
                        getattr(dialog, 'username', None)
                    )
                    if (
                        canal_norm in dialog_name
                        or canal_sem_espaco == dialog_username.replace(' ', '')
                        or canal_sem_espaco in dialog_username.replace(' ', '')
                    ):
                        target_id = dialog.id
                        logger.info(f"✅ CANAL ENCONTRADO: {dialog.name} (ID: {target_id})")
                        break

                if not target_id:
                    logger.warning(f"⚠️ Canal não encontrado: {canal_nome}. Verifique o nome/@username (pode ser o nome exato OU o @username do canal).")
                    canal['target_id'] = None
                    continue
                canal['target_id'] = target_id

                # ─── COLD START: banco vazio, pular histórico ──────────────
                # Quando o banco está recém-criado/vazio, last_id parte de 0 e o
                # polling reprocessaria os últimos posts do canal (disparos duplicados).
                # Detectamos isso e avançamos o last_id até o post mais recente,
                # processando apenas ofertas NOVAS daqui em diante.
                latest = await client.get_messages(target_id, limit=1)
                current_last = await load_last_id(canal_nome)
                if latest and current_last > latest[0].id:
                    logger.info(f"🔄 last_id ({current_last}) é maior que o último post do canal ({latest[0].id}). Trocou de canal? Resetando para 0.")
                    await save_last_id(canal_nome, 0, forcar=True)
                current_last = await load_last_id(canal_nome)
                if current_last == 0:
                    try:
                        if latest and latest[0].id:
                            await save_last_id(canal_nome, latest[0].id)
                            logger.info(f"🧊 Cold start ({canal_nome}): last_id inicializado em {latest[0].id}. Só novas ofertas serão processadas.")
                    except Exception as cold_err:
                        logger.error(f"❌ Erro no cold start ({canal_nome}): {cold_err}")

            # Remove canais que não foram encontrados
            canais = [c for c in canais if c.get('target_id')]
            if not canais:
                logger.error("❌ Nenhum canal monitorado foi encontrado. Verifique SOURCE_CHANNEL_USERNAME / EXTRA_SOURCE_CHANNELS.")
                return

            # Serializa as publicações (Story/Feed do IG + Facebook). O cooldown
            # só é registrado DEPOIS do post dar certo (~15-30s), então sem lock
            # várias mensagens em paralelo (listener + polling) passariam na
            # checagem e publicariam juntas.
            publicacao_lock = asyncio.Lock()

            # Serializa a checagem de oferta repetida + gravação no banco.
            # Sem isso, dois canais podem postar a mesma oferta ao mesmo tempo:
            # os dois passam na checagem antes de qualquer um salvar.
            dedup_lock = asyncio.Lock()

            async def process_message(message, canal=None):
                """Converte links e envia para Telegram + WhatsApp"""
                msg_text = message.message or ""
                canal = canal or {'nome': canal_principal, 'filtro': None}
                canal_filtro = canal.get('filtro')

                if not msg_text and not message.photo:
                    return False

                # ─── Filtro: Ignora mensagens sem links (comentários/avisos) ───
                if not re.search(r'https?://\S+', msg_text):
                    logger.info(f"ℹ️ Mensagem ignorada (não contém links)")
                    return False

                # ─── Filtro do canal (ex.: só AliExpress) ─────────────────────
                if canal_filtro == 'aliexpress':
                    if not re.search(r'(?:aliexpress\.com|s\.click\.ali|a\.aliexpress\.com)', msg_text, re.I):
                        logger.info(f"🚫 ({canal['nome']}) ignorada: só captura ofertas AliExpress.")
                        return False

                logger.info(f"🔥 OFERTA CAPTURADA: {msg_text[:60]}...")

                # ─── Trava anti-repetição ────────────────────────────────────
                # Cupons: deduplicados pelo CÓDIGO/TÍTULO na janela de 30 min
                # (cupons diferentes da mesma loja podem usar o mesmo link).
                # Ofertas comuns: a trava diária ("já capturada hoje") foi
                # DESATIVADA a pedido do usuário. Vale apenas a janela de 30 min
                # por link, aplicada mais abaixo em promo_duplicada_na_janela.
                eh_cupom_msg = False
                chave_cupom = ''
                try:
                    from bot.classifier import detectar_categoria
                    eh_cupom_msg = detectar_categoria(msg_text) == 'cupom'
                except Exception as cupom_err:
                    logger.warning(f"⚠️ Falha ao detectar cupom na trava anti-repetição: {cupom_err}")

                if eh_cupom_msg:
                    try:
                        from bot.services import (
                            _chave_cupom,
                            promo_chave_duplicada_na_janela,
                        )
                        chave_cupom = _chave_cupom(msg_text)
                        duplicada_cupom = await asyncio.to_thread(
                            promo_chave_duplicada_na_janela, chave_cupom
                        )
                        if duplicada_cupom:
                            logger.info(
                                "⏭️ Cupom já postado nesta janela de 30 min, "
                                "ignorado. "
                                f"[id={duplicada_cupom.id} "
                                f"criado_em={duplicada_cupom.criado_em} "
                                f"chave={duplicada_cupom.link_produto_chave!r} "
                                f"titulo={duplicada_cupom.titulo!r}]"
                            )
                            return True
                        logger.info(
                            f"🎟️ Cupom detectado (chave={chave_cupom!r}); "
                            "sem duplicata na janela de 30 min."
                        )
                    except Exception as cupom_dedup_err:
                        logger.error(f"❌ Erro na trava de cupom: {cupom_dedup_err}")
                # Trava diária por oferta repetida (promo_repetida_recente)
                # DESATIVADA: só a janela de 30 min deve bloquear reposts.
                # try:
                #     from bot.services import promo_repetida_recente
                #     repetida = await asyncio.to_thread(promo_repetida_recente, msg_text)
                #     if repetida:
                #         logger.info(
                #             "⏭️ Oferta já capturada hoje, ignorada. "
                #             f"[id={repetida.id} "
                #             f"criado_em={repetida.criado_em} "
                #             f"titulo={repetida.titulo!r} "
                #             f"preco={repetida.preco!r} "
                #             f"produto_chave={repetida.produto_chave!r} "
                #             f"url_chave={repetida.url_chave!r}]"
                #         )
                #         return True
                # except Exception as repetida_err:
                #     logger.error(f"❌ Erro na trava anti-repetição: {repetida_err}")

                # ─── Deduplicação: já foi postada antes? ─────────────────────
                # DESATIVADO a pedido do usuário: nenhuma oferta é ignorada
                # como "já postada". Todas passam pelos filtros abaixo.
                # from bot.services import promo_ja_postada
                # try:
                #     ja_postada = await asyncio.to_thread(promo_ja_postada, msg_text)
                #     if ja_postada:
                #         logger.info("⏭️ Oferta já postada anteriormente, ignorada.")
                #         return True
                # except Exception as dup_err:
                #     logger.error(f"❌ Erro deduplicação: {dup_err}")

                # ─── Filtro de Palavras Proibidas (Blacklist) ────────────────
                blacklist = ['youtube', 'youtu.be', 'terabyte', 'terabyteshop']
                if any(word in msg_text.lower() for word in blacklist):
                    logger.info(f"🚫 Mensagem ignorada (palavra na blacklist encontrada)")
                    return False

                # ─── Converte links e processa texto ─────────────────────────
                from bot.services import send_whatsapp_message, strip_promo_footer, normaliza_emoji_inicial, substituir_nomes_canais, remover_cabecalho_alerta

                channel_name = getattr(settings, 'PERSONAL_CHANNEL_NAME', 'Seu Canal')

                modified_text = msg_text

                # Remove cabeçalho de canal ('🚨 Alerta de Promo:') — não é
                # conteúdo da oferta.
                modified_text = remover_cabecalho_alerta(modified_text)

                # Remove divulgação do grupo/jogo de Impulso sem perder a oferta
                modified_text = _remover_divulgacao_grupo_impulso(modified_text)

                # 1. Substitui nomes de canais, sem alterar cupons
                modified_text = substituir_nomes_canais(modified_text, channel_name)

                # 2. Remove o rodapé antigo do grupo (Limpeza Pesada)
                # Remove o emoji da sacola (várias versões) e qualquer linha residual
                modified_text = modified_text.replace('🛍️', '').replace('🛍', '')
                modified_text = re.sub(r'(?i)Grupo de promos.*?(?:\n|$)', '', modified_text)
                modified_text = re.sub(r'https?://t\.me/\S+', '', modified_text)
                # Substitui links do Linktree pelo link personalizado
                modified_text = re.sub(r'https?://linktr\.ee/\S+', 'https://links.andreindica.com.br/', modified_text)
                modified_text = strip_promo_footer(modified_text)
                modified_text = normaliza_emoji_inicial(modified_text)
                # Remove linhas vazias excessivas
                modified_text = re.sub(r'\n\s*\n', '\n\n', modified_text)

                # 3. Converte links de produtos
                links = re.findall(r'(https?://\S+)', modified_text)
                converted_any = False
                has_ali = False
                # URLs reais obtidas ao expandir redirecionadores (seuhardware,
                # pcdofafa, Awin...). Ajudam a identificar o mesmo produto
                # entre canais que usam links/rastreios diferentes.
                links_resolvidos = []

                # Deduplicação: remove links repetidos mantendo a ordem
                seen_links = []
                unique_links = []
                for lnk in links:
                    # Normaliza para comparação (remove parâmetros de rastreio)
                    # Exceção: links Awin possuem o destino real nos parâmetros.
                    if 'awin1.com' in lnk or 'tidd.ly' in lnk:
                        lnk_norm = lnk
                    else:
                        lnk_norm = lnk.split('?')[0].rstrip('/')
                        
                    if lnk_norm not in seen_links:
                        seen_links.append(lnk_norm)
                        unique_links.append(lnk)
                    else:
                        # Remove duplicata do texto diretamente
                        modified_text = modified_text.replace(lnk, '', 1)
                # Remove linhas vazias geradas pela remoção das duplicatas
                modified_text = re.sub(r'\n{3,}', '\n\n', modified_text)

                for link in unique_links:
                    is_telegram = 't.me/' in link
                    is_tecnan = 'tecnan.com.br' in link
                    is_awin = 'awin1.com' in link or 'tidd.ly' in link
                    is_amazon = 'amazon.com.br' in link or 'amzn.to' in link or 'link.amazon' in link or 'aoferta.net' in link
                    is_shopee = 'shopee.com.br' in link or 's.shopee' in link
                    is_ofertei = 'ofertei.net' in link
                    is_ml = 'mercadolivre' in link or 'meli.la' in link or 'mlstatic' in link or is_ofertei
                    is_ali = 'aliexpress.com' in link or 's.click.ali' in link
                    is_kabum = 'kabum.com.br' in link
                    is_magalu = 'magazineluiza.com.br' in link or 'magalu.com' in link or 'mgl.io' in link
                    is_pcdofafa = 'pcdofafa.com.br' in link
                    is_seuhardware = 'seuhardware.com' in link

                    if is_telegram or is_tecnan:
                        modified_text = modified_text.replace(link, '') # Remove links de outros telegrams
                        continue

                    if is_awin:
                        # Extrai a URL real do produto e gera novo link com nosso ID
                        import urllib.parse as _urlparse
                        from bot.services import convert_awin_link
                        extracted_url = None
                        if 'ued=' in link:
                            try:
                                ued_value = link.split('ued=')[1].split('&')[0]
                                extracted_url = _urlparse.unquote(ued_value)
                            except:
                                pass
                        if extracted_url:
                            links_resolvidos.append(extracted_url)
                            new_awin = await asyncio.to_thread(
                                convert_awin_link, extracted_url
                            )
                            if new_awin:
                                modified_text = modified_text.replace(link, new_awin)
                                converted_any = True
                                continue
                        converted_any = True
                        continue

                    if is_pcdofafa:
                        # Canal PC DO FAFA: o link pcdofafa.com.br faz redirect
                        # via <meta http-equiv="refresh">. Extrai a URL real e
                        # converte para afiliado.
                        try:
                            import re as _re_pcd
                            resp = await asyncio.to_thread(
                                requests.get,
                                link,
                                allow_redirects=True,
                                timeout=8,
                                headers={"User-Agent": "Mozilla/5.0"},
                            )
                            html_pcd = resp.text
                            real_url = ''
                            m_refresh = _re_pcd.search(
                                r'http-equiv=["\']refresh["\']\s+content=["\']\d+;\s*url=([^"\']+)',
                                html_pcd,
                                _re_pcd.IGNORECASE,
                            )
                            if m_refresh:
                                real_url = m_refresh.group(1).strip()
                            if real_url:
                                links_resolvidos.append(real_url)
                                converted = await _converter_link_com_retry(real_url)
                                if converted:
                                    modified_text = modified_text.replace(link, converted)
                                    converted_any = True
                                    if 'aliexpress' in real_url:
                                        has_ali = True
                                    continue
                        except Exception as pcd_err:
                            logger.warning(f"⚠️ pcdofafa expand erro: {pcd_err}")
                        # Se falhou, não conta como convertido (vai sair no 'nenhum link')
                        continue

                    if is_seuhardware:
                        # Canal Iskandar (seuhardware.com/s/...): o link faz
                        # redirect HTTP (301/302) para a loja de destino
                        # (Mercado Livre, Amazon, Shopee, AliExpress, etc.).
                        # Seguimos o redirect e convertemos para o NOSSO link
                        # de afiliado da loja encontrada.
                        try:
                            resp_seu = await asyncio.to_thread(
                                requests.get,
                                link,
                                allow_redirects=True,
                                timeout=12,
                                headers={"User-Agent": "Mozilla/5.0"},
                            )
                            real_url = resp_seu.url or ''
                            if _eh_link_grupo(real_url):
                                # Remove a linha do convite e continua com a oferta.
                                modified_text = '\n'.join(
                                    ln for ln in modified_text.splitlines() if link not in ln
                                )
                                modified_text = re.sub(r'\n{3,}', '\n\n', modified_text)
                                logger.info("🧹 Link de grupo removido da oferta")
                                continue
                            if real_url and real_url != link:
                                links_resolvidos.append(real_url)
                                converted = await _converter_link_com_retry(real_url)
                                if converted:
                                    if 'aliexpress' in real_url:
                                        has_ali = True
                                    modified_text = modified_text.replace(link, converted)
                                    modified_text = re.sub(r'\n{3,}', '\n\n', modified_text)
                                    converted_any = True
                                    continue
                                logger.warning(f"⚠️ seuhardware sem conversão: {real_url[:120]}")
                        except Exception as seu_err:
                            logger.warning(f"⚠️ seuhardware expand erro: {seu_err}")
                        # Se falhou, não conta como convertido (vai sair no 'nenhum link')
                        continue

                    if canal_filtro == 'aliexpress':
                        # Canal configurado para capturar SÓ AliExpress: remove
                        # qualquer outro link de loja e mantém apenas os da Ali.
                        if is_ali:
                            converted = await _converter_link_com_retry(link)
                            if converted:
                                has_ali = True
                                modified_text = modified_text.replace(link, converted)
                                modified_text = re.sub(r'\n{3,}', '\n\n', modified_text)
                                converted_any = True
                        elif is_amazon or is_shopee or is_ml or is_kabum or is_magalu or is_awin or is_pcdofafa or is_seuhardware:
                            modified_text = modified_text.replace(link, '')
                            modified_text = re.sub(r'\n{3,}', '\n\n', modified_text)
                        continue

                    if any([is_amazon, is_shopee, is_ml, is_ali, is_kabum, is_magalu]):
                        converted = await _converter_link_com_retry(link)
                        if converted:
                            if is_ali:
                                # O canal fonte já fornece links separados para App e PC com labels prontas.
                                # Apenas converte cada URL para o link de afiliado e substitui no lugar.
                                has_ali = True
                            
                            modified_text = modified_text.replace(link, converted)
                            # Remove linhas vazias extras
                            modified_text = re.sub(r'\n{3,}', '\n\n', modified_text)
                            converted_any = True

                # Se não encontrar links de lojas (Amazon, AliExpress, etc.), ignoramos a mensagem.
                if not converted_any:
                    logger.info("🚫 Mensagem ignorada (nenhum link de loja detectado).")
                    return False

                # ─── Trava de oferta repetida por LINK (janela de 30 min) ─────────
                # Compara o link canônico do produto (sem preço/rastreio),
                # inclusive o destino real de encurtadores/redirecionadores.
                # Vale entre canais: se a oferta já foi postada nesta janela
                # de 30 min por qualquer canal, a segunda é ignorada. A janela
                # é móvel: conta 30 min a partir do horário da oferta
                # (postada às 11:30, só pode ser repostada a partir das 12:00).
                chave_link_produto = ''
                urls_dedup = _links_relevantes_para_dedup(
                    links_resolvidos
                    + re.findall(r'(https?://\S+)', modified_text)
                    + links
                )
                # Encurtadores (Shopee, AliExpress, etc.) escondem o ID do
                # produto; segue o redirecionamento para comparar o destino.
                if not eh_cupom_msg and urls_dedup:
                    urls_dedup = await asyncio.to_thread(
                        _expandir_urls_para_dedup, urls_dedup
                    )
                if not eh_cupom_msg and urls_dedup:
                    try:
                        from bot.services import (
                            promo_duplicada_na_janela,
                            _chave_link_produto,
                        )
                        duplicada = await asyncio.to_thread(
                            promo_duplicada_na_janela, *urls_dedup
                        )
                        if duplicada:
                            logger.info(
                                "⏭️ Oferta já postada nesta janela de 30 min "
                                "(mesmo link), ignorada. "
                                f"[id={duplicada.id} "
                                f"criado_em={duplicada.criado_em} "
                                f"chave={duplicada.link_produto_chave!r} "
                                f"titulo={duplicada.titulo!r}]"
                            )
                            return True
                        # Prefere a chave específica do produto (ex.:
                        # 'shopee:123:456') à chave genérica de um link curto
                        # (ex.: 's.shopee.com.br/abc'), que muda a cada geração.
                        # Chaves que não identificam um produto (live,
                        # compartilhar, home) são descartadas: gravá-las
                        # bloquearia ofertas diferentes na janela de 30 min.
                        from bot.services import _link_identifica_produto
                        chaves_calculadas = []
                        for url_dedup in urls_dedup:
                            chave = _chave_link_produto(url_dedup)
                            if (
                                chave
                                and _link_identifica_produto(chave)
                                and chave not in chaves_calculadas
                            ):
                                chaves_calculadas.append(chave)
                        if chaves_calculadas:
                            chave_link_produto = next(
                                (c for c in chaves_calculadas if ':' in c),
                                chaves_calculadas[0],
                            )
                    except Exception as dedup_err:
                        logger.error(f"❌ Erro na trava por link: {dedup_err}")

                # 4. Adiciona o novo rodapé do site
                # Remove seções PELO PC residuais e outras linhas de rodapé do canal fonte
                modified_text = re.sub(r'(?i)\n?⬇️?\s*PELO PC\s*\n?', '', modified_text)
                modified_text = re.sub(r'\n{3,}', '\n\n', modified_text)
                modified_text = modified_text.strip()

                if modified_text:
                    # Detecta categoria ANTES de adicionar aviso,
                    # para não colar "cupons" em produtos não-cupom.
                    from bot.classifier import detectar_categoria
                    from bot.services import _linha_titulo
                    eh_cupom = detectar_categoria(
                        modified_text, titulo=_linha_titulo(modified_text)
                    ) == 'cupom'

                    if eh_cupom:
                        # Aviso específico de cupom — só para ofertas de cupom mesmo.
                        if AVISO_CUPOM not in modified_text:
                            modified_text += f"\n\n{AVISO_CUPOM}"
                    else:
                        # Produto não-cupom: usa aviso genérico, sem a palavra "cupom"
                        # para não contaminar a classificação futura.
                        gen_aviso = "⏳ A promoção pode encerrar a qualquer momento."
                        if AVISO_CUPOM not in modified_text and gen_aviso not in modified_text:
                            modified_text += f"\n\n{gen_aviso}"
                    if has_ali:
                        modified_text += (
                            "\n\n💡 Dica: Comprando pelo aplicativo o desconto pode ser maior por causa das moedas.\n"
                            "Após clicar no link acima, você será direcionado para a página de moedas. Clique no primeiro anúncio.\n"
                            "Se o produto não aparecer, clique em 'DO BRASIL'."
                        )
                    modified_text += f"\n\n{_AVISO_PROMOCAO}"


                # ─── Baixa foto ──────────────────────────────────────────────
                photo_path = None
                imagem_cupom_usada = False
                temp_dir = os.path.join(os.getcwd(), 'tmp_photos')
                os.makedirs(temp_dir, exist_ok=True)

                # 0) Se a oferta é CUPOM: usa a imagem fixa da loja (pasta
                # media/cupom/) — não usa imagem do link nem do canal.
                eh_cupom = False
                try:
                    from bot.classifier import detectar_categoria
                    from bot.services import _linha_titulo
                    eh_cupom = detectar_categoria(
                        modified_text, titulo=_linha_titulo(modified_text)
                    ) == 'cupom'
                except Exception as cup_err:
                    logger.warning(f"⚠️ Falha ao detectar categoria cupom: {cup_err}")

                if eh_cupom:
                    logger.info("🛑 Cupom detectado - captura bloqueada (janela de 30 min ativa).")
                    return True

                # 1) Tenta a imagem principal da PÁGINA do produto (link da
                # oferta). Assim a imagem vem limpa, sem marca d'água do canal.
                if not photo_path and getattr(settings, 'IMAGEM_DA_PAGINA_PRODUTO', True):
                    try:
                        from bot.services import baixar_imagem_produto
                        img_prod = await asyncio.to_thread(baixar_imagem_produto, msg_text, temp_dir)
                        if img_prod and os.path.exists(img_prod):
                            photo_path = img_prod
                            logger.info("🖼️ Usando imagem da página do produto.")
                    except Exception as img_err:
                        logger.warning(f"⚠️ Falha ao baixar imagem do produto: {img_err}")

                # 2) Fallback: usa a foto capturada do canal. Como é a foto do
                # próprio canal (com rodapé/crédito dele), corta 100px da base.
                # Se a imagem original do produto foi obtida acima, NÃO corta.
                if not photo_path and message.photo:
                    photo_path = await message.download_media(file=temp_dir)
                    if photo_path:
                        photo_path = os.path.abspath(photo_path)
                        try:
                            from bot.services import cortar_rodape_imagem
                            photo_path = await asyncio.to_thread(cortar_rodape_imagem, photo_path, 100)
                            logger.info("✂️ Rodapé da foto do canal cortado (100px).")
                        except Exception as crop_err:
                            logger.warning(f"⚠️ Falha ao cortar rodapé da foto do canal: {crop_err}")
                        logger.info(f"📸 Foto capturada baixada: {photo_path}")

                # Marca d'água 'Andre Indica' no canto inferior esquerdo
                # (não aplica na imagem fixa de cupom, que já é pronta)
                if photo_path and not imagem_cupom_usada:
                    from bot.services import adicionar_watermark
                    photo_path = await asyncio.to_thread(adicionar_watermark, photo_path)

                # ─── Salva a promo no banco para a página web ─────────────────
                promo_id = None
                try:
                    from bot.services import (
                        save_promo_to_db,
                        _chave_dedup,
                        promo_duplicada_na_janela,
                        promo_chave_duplicada_na_janela,
                    )
                    # Chave estável baseada no link BRUTO + preço (msg_text),
                    # para não ignorar ofertas novas do mesmo produto com preço/cupom diferente.
                    chave_estavel = _chave_dedup(msg_text)
                    async with dedup_lock:
                        # Recheca dentro do lock: dois canais podem ter passado
                        # na checagem anterior ao mesmo tempo. Só a primeira
                        # oferta é salva/postada; a segunda é ignorada.
                        if eh_cupom_msg:
                            duplicada_cupom = await asyncio.to_thread(
                                promo_chave_duplicada_na_janela, chave_cupom
                            )
                            if duplicada_cupom:
                                logger.info(
                                    "⏭️ Cupom já postado nesta janela de 30 min, "
                                    "ignorado. "
                                    f"[id={duplicada_cupom.id} "
                                    f"criado_em={duplicada_cupom.criado_em} "
                                    f"chave={duplicada_cupom.link_produto_chave!r} "
                                    f"titulo={duplicada_cupom.titulo!r}]"
                                )
                                if photo_path and not imagem_cupom_usada:
                                    try:
                                        os.remove(photo_path)
                                    except Exception:
                                        pass
                                return True
                        elif urls_dedup:
                            duplicada = await asyncio.to_thread(
                                promo_duplicada_na_janela, *urls_dedup
                            )
                            if duplicada:
                                logger.info(
                                    "⏭️ Oferta já postada nesta janela de 30 min "
                                    "(mesmo link), ignorada. "
                                    f"[id={duplicada.id} "
                                    f"criado_em={duplicada.criado_em} "
                                    f"chave={duplicada.link_produto_chave!r} "
                                    f"titulo={duplicada.titulo!r}]"
                                )
                                if photo_path and not imagem_cupom_usada:
                                    try:
                                        os.remove(photo_path)
                                    except Exception:
                                        pass
                                return True
                        promo_id = await asyncio.to_thread(
                            save_promo_to_db,
                            modified_text,
                            photo_path,
                            canal['nome'],
                            chave_estavel,
                            chave_cupom if eh_cupom_msg else chave_link_produto,
                        )
                    logger.info("💾 Promo salva no banco de dados")
                except Exception as db_err:
                    logger.error(f"❌ Erro ao salvar promo no banco: {db_err}")

                # Sem aviso nos alertas (Telegram/WhatsApp de usuários)
                texto_para_alertas = _texto_sem_rodape(modified_text)

                # ─── Categoria da oferta (para filtro dos alertas) ──────────
                # O alerta só dispara se o produto aparecer na categoria
                # correspondente à keyword (ex.: alerta 'placa de video rtx
                # 5060' NÃO dispara para um cupom, mesmo com link da placa).
                categoria_oferta = None
                if promo_id:
                    try:
                        from bot.models import Promo
                        cat = await sync_to_async(
                            lambda: Promo.objects.filter(pk=promo_id)
                            .values_list('categoria', flat=True).first()
                        )()
                        if cat:
                            categoria_oferta = cat
                    except Exception as cat_err:
                        logger.warning(f"⚠️ Erro ao obter categoria da promo: {cat_err}")
                if not categoria_oferta:
                    try:
                        from bot.classifier import detectar_categoria
                        from bot.services import _linha_titulo
                        categoria_oferta = detectar_categoria(
                            texto_para_alertas, titulo=_linha_titulo(texto_para_alertas)
                        )
                    except Exception as cat_err2:
                        logger.warning(f"⚠️ Erro ao detectar categoria da oferta: {cat_err2}")

                # ─── Redireciona os links de loja para a página do site ──────
                # No Telegram/WhatsApp, quem clica no link vai para a página
                # da promoção aqui no site; de lá o botão 'Comprar' leva ao
                # produto (link de afiliado). O rodapé não é alterado.
                if promo_id:
                    try:
                        from bot.services import trocar_links_loja_por_site
                        base_site = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
                        if base_site:
                            modified_text = trocar_links_loja_por_site(modified_text, promo_id, base_site)
                            logger.info("🔗 Links de loja -> página do site (Telegram/WhatsApp)")
                    except Exception as relink_err:
                        logger.warning(f"⚠️ Erro ao trocar links para o site: {relink_err}")

                # ─── Envia para o Telegram ───────────────────────────────────
                try:
                    from html import escape as _html_escape
                    # Sem rodapé de canais e sem aviso de promoção; mantém o ⚠️ Aviso.
                    # Se não for AliExpress, insere a dica de comprar pelo app.
                    corpo_tg = _texto_sem_rodape(modified_text)
                    if not has_ali:
                        corpo_tg += f"\n\n{_AVISO_APP_LOJA}"
                    corpo_tg += f"\n\n{_AVISO_AUTOMATICO}"
                    corpo_tg = _html_escape(corpo_tg)
                    texto_telegram = corpo_tg
                    if photo_path and os.path.exists(photo_path):
                        corte = corpo_tg[:1024]
                        # Não corta no meio de uma entidade (&amp; etc.)
                        amp = corte.rfind('&')
                        if amp != -1 and ';' not in corte[amp:]:
                            corte = corte[:amp]
                        await client.send_file(group_id, photo_path, caption=corte, parse_mode='html')
                        logger.info("✅ Enviado para Telegram (com foto)")
                    else:
                        await client.send_message(group_id, texto_telegram, parse_mode='html')
                        logger.info("✅ Enviado para Telegram (só texto)")
                except Exception as tg_err:
                    logger.error(f"❌ Erro Telegram: {tg_err}")

                # ─── Envia para o WhatsApp ───────────────────────────────────
                try:
                    texto_whatsapp = _texto_sem_rodape(modified_text)
                    if not has_ali:
                        texto_whatsapp += f"\n\n{_AVISO_APP_LOJA}"
                    texto_whatsapp += f"\n\n{_AVISO_AUTOMATICO}"
                    enviado_wa = send_whatsapp_message(texto_whatsapp, photo_path)
                    if enviado_wa:
                        logger.info("✅ Enviado para WhatsApp")
                    else:
                        logger.error("❌ WhatsApp: envio falhou (ver status acima)")
                except Exception as wa_err:
                    logger.error(f"❌ Erro WhatsApp: {wa_err}")

                # ─── Dispara alertas para usuários do Bot ────────────────────
                # Usa o texto ANTES de trocar os links pelo site, para que
                # keywords como 'aliexpress', 'amazon', etc. ainda casem com a URL original.
                try:
                    from bot.alert_sender import send_alerts
                    await asyncio.to_thread(send_alerts, texto_para_alertas, photo_path, categoria_oferta)
                    logger.info("🔔 Alertas de usuários verificados/enviados")
                except Exception as alert_err:
                    logger.error(f"❌ Erro ao enviar alertas: {alert_err}")

                # ─── Dispara alertas do André Alerta (site → WhatsApp) ──────
                # Usa o texto com os links já trocados pela página do site,
                # igual ao Telegram/grupo do WhatsApp. O matching de keyword
                # continua no texto original (texto_para_alertas).
                try:
                    from bot.alert_site import send_alerts_site
                    texto_para_alertas_site = _texto_sem_rodape(modified_text)
                    await asyncio.to_thread(
                        send_alerts_site, texto_para_alertas, photo_path, categoria_oferta,
                        offer_text_site=texto_para_alertas_site,
                    )
                    logger.info("🔔 André Alerta (WhatsApp) verificado/enviado")
                except Exception as site_err:
                    logger.error(f"❌ Erro no André Alerta: {site_err}")

                # ─── Publicações (IG Story + IG Feed + Facebook) ───────────
                # Dentro do lock: checar permissão → publicar → registrar são
                # atômicos. Assim, quando duas ofertas chegam juntas, a segunda
                # espera a primeira terminar (e registrar o cooldown) antes de
                # checar — não publica mais do que uma por janela.
                # Link da página do produto no site (sticker clicável no Story /
                # link compartilhado no Facebook)
                pagina_url = ''
                if promo_id:
                    base_site = (getattr(settings, 'SITE_URL', '') or '').rstrip('/')
                    if base_site:
                        pagina_url = f"{base_site}/promos/{promo_id}/"
                async with publicacao_lock:
                    try:
                        from bot.instagram_stories import post_instagram_story
                        from bot.story_gate import pode_publicar_story, registrar_publicacao

                        if categoria_oferta in _CATS_BLOQUEADAS_REDES:
                            logger.info(f"⏸️ Story não publicado: categoria '{categoria_oferta}'.")
                        else:
                            permitido, motivo = await asyncio.to_thread(pode_publicar_story)
                            if not permitido:
                                logger.info(f"⏸️ Story adiado ({motivo}). Promo segue salva no banco e no Telegram.")
                            else:
                                publicou = await asyncio.to_thread(post_instagram_story, modified_text, photo_path, pagina_url)
                                if publicou:
                                    await asyncio.to_thread(registrar_publicacao)
                                    logger.info("📸 Story publicado no Instagram (dentro da janela/cooldown).")
                    except Exception as ig_err:
                        logger.error(f"❌ Erro Instagram: {ig_err}")

                    # ─── Publica no FEED do Instagram ───────────────────────
                    try:
                        from bot.instagram_stories import post_instagram_feed
                        from bot.story_gate import pode_publicar_story, registrar_publicacao as registrar_feed

                        if categoria_oferta in _CATS_BLOQUEADAS_REDES:
                            logger.info(f"⏸️ Feed não publicado: categoria '{categoria_oferta}'.")
                        else:
                            permitido_feed, motivo_feed = await asyncio.to_thread(
                                pode_publicar_story, chave='ultima_publicacao_ig_feed'
                            )
                            if not permitido_feed:
                                logger.info(f"⏸️ Instagram feed adiado ({motivo_feed}). Promo segue salva no banco e no Telegram.")
                            else:
                                publicou_feed = await asyncio.to_thread(post_instagram_feed, modified_text, photo_path, pagina_url)
                                if publicou_feed:
                                    await asyncio.to_thread(registrar_feed, chave='ultima_publicacao_ig_feed')
                                    logger.info("🖼️ Oferta publicada no feed do Instagram.")
                    except Exception as igf_err:
                        logger.error(f"❌ Erro Instagram feed: {igf_err}")

                    # ─── Publica na Página do Facebook ─────────────────────
                    try:
                        from bot.facebook_poster import post_facebook
                        from bot.story_gate import pode_publicar_story, registrar_publicacao

                        if categoria_oferta in _CATS_BLOQUEADAS_REDES:
                            logger.info(f"⏸️ Facebook não publicado: categoria '{categoria_oferta}'.")
                        else:
                            permitido_fb, motivo_fb = await asyncio.to_thread(
                                pode_publicar_story, chave='ultima_publicacao_fb'
                            )
                            if not permitido_fb:
                                logger.info(f"⏸️ Facebook adiado ({motivo_fb}). Promo segue salva no banco e no Telegram.")
                            else:
                                publicou_fb = await asyncio.to_thread(post_facebook, modified_text, photo_path, pagina_url)
                                if publicou_fb:
                                    await asyncio.to_thread(registrar_publicacao, chave='ultima_publicacao_fb')
                                    logger.info("📣 Oferta publicada no Facebook.")
                                else:
                                    logger.info("ℹ️ Facebook: nada publicado (não configurado ou falhou).")
                    except Exception as fb_err:
                        logger.error(f"❌ Erro Facebook: {fb_err}")

                    # ─── Publica nos STORIES do Facebook ────────────────────
                    try:
                        from bot.facebook_poster import post_facebook_story
                        from bot.story_gate import pode_publicar_story, registrar_publicacao

                        if categoria_oferta in _CATS_BLOQUEADAS_REDES:
                            logger.info(f"⏸️ Facebook story não publicado: categoria '{categoria_oferta}'.")
                        else:
                            permitido_fbs, motivo_fbs = await asyncio.to_thread(
                                pode_publicar_story, chave='ultima_publicacao_fb_story'
                            )
                            if not permitido_fbs:
                                logger.info(f"⏸️ Facebook story adiado ({motivo_fbs}).")
                            else:
                                publicou_fbs = await asyncio.to_thread(post_facebook_story, modified_text, photo_path, pagina_url)
                                if publicou_fbs:
                                    await asyncio.to_thread(registrar_publicacao, chave='ultima_publicacao_fb_story')
                                    logger.info("📱 Story publicado no Facebook.")
                                else:
                                    logger.info("ℹ️ Facebook story: nada publicado (não configurado ou falhou).")
                    except Exception as fbs_err:
                        logger.error(f"❌ Erro Facebook story: {fbs_err}")

                # ─── Limpa foto após 90s ─────────────────────────────────────
                # (não remove a imagem fixa de cupom, que é compartilhada)
                if photo_path and not imagem_cupom_usada:
                    async def cleanup(path):
                        await asyncio.sleep(90)
                        try:
                            if os.path.exists(path):
                                os.remove(path)
                        except Exception:
                            pass
                    asyncio.create_task(cleanup(photo_path))

                return True

            # ─── Processamento serializado por canal ────────────────────────
            async def processar_mensagem_com_trava(msg, canal):
                """Processa uma mensagem com lock por canal e retry controlado.

                - Serializa mensagens do MESMO canal: evita que 3 ofertas
                  simultâneas disputem a conversão de link e o last_id.
                - Se process_message falhar, tenta de novo NA HORA, ainda
                  dentro do lock. O retry precisa ser aqui: se a mensagem
                  falhasse e uma seguinte tivesse sucesso, o last_id passaria
                  à frente e a falha nunca mais seria reprocessada.
                - Depois de N tentativas, loga o erro completo (com id e
                  texto) e avança o last_id para não travar a fila.
                """
                canal_nome = canal['nome']
                chave = (canal_nome, msg.id)
                async with _lock_do_canal(canal_nome):
                    last_id = await load_last_id(canal_nome)
                    if msg.id <= last_id or chave in _processing_ids:
                        return
                    _processing_ids.add(chave)
                    try:
                        for tentativa in range(1, _MAX_TENTATIVAS_PROCESSAMENTO + 1):
                            try:
                                await process_message(msg, canal)
                                _falhas_processamento.pop(chave, None)
                                break
                            except Exception:
                                logger.exception(
                                    f"❌ Falha ao processar mensagem {msg.id} "
                                    f"({canal_nome}), tentativa {tentativa}/"
                                    f"{_MAX_TENTATIVAS_PROCESSAMENTO}. "
                                    f"texto={(getattr(msg, 'text', '') or '')[:200]!r}"
                                )
                                if tentativa >= _MAX_TENTATIVAS_PROCESSAMENTO:
                                    _falhas_processamento[chave] = tentativa
                                    logger.error(
                                        f"⚠️ Desistindo da mensagem {msg.id} "
                                        f"({canal_nome}) após {tentativa} falhas; "
                                        "avançando last_id para liberar a fila."
                                    )
                                    break
                                await asyncio.sleep(1)
                    finally:
                        _processing_ids.discard(chave)
                    # Avança após sucesso (inclusive quando a oferta foi
                    # ignorada por deduplicação, que também é sucesso) ou
                    # após esgotar as tentativas (para a fila não travar).
                    await save_last_id(canal_nome, msg.id)

            # ─── LISTENER (Tempo Real) — um por canal ────────────────────────
            async def registrar_listener(canal):
                target_id = canal['target_id']

                @client.on(events.NewMessage(chats=target_id))
                async def handler(event):
                    await processar_mensagem_com_trava(event.message, canal)

            for canal in canais:
                await registrar_listener(canal)

            # ─── POLLING INTELIGENTE — itera todos os canais ────────────────
            async def smart_polling():
                while True:
                    try:
                        for canal in canais:
                            target_id = canal['target_id']
                            canal_nome = canal['nome']
                            last_id = await load_last_id(canal_nome)
                            messages = await client.get_messages(
                                target_id, limit=10, min_id=last_id
                            )
                            if messages:
                                for msg in reversed(list(messages)):
                                    await processar_mensagem_com_trava(msg, canal)
                        await client.get_me()
                        logger.info("💓 Check-up automático realizado")
                    except Exception as e:
                        logger.error(f"Erro no polling: {e}")
                    await asyncio.sleep(30)

            logger.info(f"🚀 MONITOR AUTÔNOMO INICIADO! Canais: {[c['nome'] for c in canais]}")
            await asyncio.gather(
                client.run_until_disconnected(),
                smart_polling()
            )

        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.warning('Monitor parado pelo usuário.')
        except Exception as e:
            logger.error(f"Erro Crítico: {e}")
