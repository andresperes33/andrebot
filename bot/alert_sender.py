"""
Função utilitária para enviar alertas de promoções
para os usuários que possuem palavras-chave compatíveis.
"""
import logging
import unicodedata
import requests as http_requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ─── Grupos de sinônimos tech ─────────────────────────────────────────────────
# Qualquer termo do grupo casa com qualquer outro
SYNONYM_GROUPS = [
    {'placa de video', 'placa de vídeo', 'placa grafica', 'placa gráfica', 'gpu', 'vga', 'video card', 'rtx', 'gtx', 'rx', 'radeon'},
    {'processador', 'cpu', 'proc', 'ryzen', 'core i3', 'core i5', 'core i7', 'core i9', 'intel core'},
    {'memoria ram', 'ram', 'memória ram', 'memoria', 'memória', 'ddr4', 'ddr5'},
    {'notebook', 'laptop', 'computador portatil', 'computador portátil', 'macbook'},
    {'celular', 'smartphone', 'telefone', 'phone', 'iphone', 'galaxy'},
    {'televisao', 'tv', 'smart tv', 'televisão', 'monitor tv'},
    {'geladeira', 'refrigerador', 'frigorifico'},
    {'airfryer', 'air fryer', 'fritadeira eletrica', 'fritadeira elétrica'},
    {'monitor'},
    {'teclado mecanico', 'teclado mecânico', 'teclado'},
    {'fone de ouvido', 'headphone', 'headset', 'auricular', 'fone', 'airpods', 'buds'},
    {'ssd', 'solid state', 'hd ssd', 'nvme', 'm2 ssd'},
    {'hd externo', 'hd', 'disco rigido', 'disco rígido', 'hard drive'},
    {'placa mae', 'placa mãe', 'motherboard', 'mainboard'},
    {'fonte', 'fonte de alimentacao', 'fonte atx', 'psu'},
    {'gabinete', 'case', 'chassis', 'caixa pc'},
    {'water cooler', 'watercooler', 'cooler agua', 'refrigeracao liquida', 'refrigeração líquida'},
    {'cooler', 'ventoinha', 'fan cooler', 'air cooler'},
    {'impressora', 'printer'},
    {'kindle', 'e-reader', 'ereader', 'leitor digital'},
]


def normalize(text: str) -> str:
    """Remove acentos e converte para minúsculas."""
    nfkd = unicodedata.normalize('NFD', text.lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def get_plural_variants(term: str) -> set[str]:
    """
    Gera variantes de singular e plural para português.
    Exemplos:
      monitor     → {monitor, monitores}
      monitores   → {monitores, monitor}
      placa       → {placa, placas}
      placas      → {placas, placa}
      processador → {processador, processadores}
    """
    variants = {term}
    if term.endswith('oes'):       # impressoes → impressao
        variants.add(term[:-3] + 'ao')
        variants.add(term[:-3] + 'ão')
    elif term.endswith('ões'):     # impressões → impressão
        variants.add(term[:-3] + 'ao')
        variants.add(term[:-3] + 'ão')
    elif term.endswith('es') and len(term) > 4:
        base = term[:-2]           # monitores → monitor
        variants.add(base)
        variants.add(base + 's')   # monitors (ingles)
    elif term.endswith('s') and len(term) > 3:
        base = term[:-1]           # placas → placa
        variants.add(base)
        variants.add(base + 'es')  # placa → placaes (raro, mas cobre casos)
    else:
        variants.add(term + 's')   # placa → placas
        variants.add(term + 'es')  # monitor → monitores
    return variants


def expand_with_synonyms(keyword: str) -> list[str]:
    """
    Retorna o keyword + todos os sinônimos equivalentes + variantes plural/singular.
    Exemplo: 'placa de vídeo' → ['placa de video', 'placa grafica', 'gpu', 'vga', ...]
             'monitores'      → ['monitores', 'monitor', 'display', 'tela', ...]
    """
    kw_norm = normalize(keyword)

    # Gera variantes plural/singular do próprio termo
    base_variants = get_plural_variants(kw_norm)
    expanded = set(base_variants)

    # Para cada variante, verifica sinônimos
    for variant in base_variants:
        for group in SYNONYM_GROUPS:
            group_norm = {normalize(s) for s in group}
            if any(term in variant or variant in term for term in group_norm):
                # Adiciona todos os sinônimos + suas formas plural/singular
                for syn in group_norm:
                    expanded.update(get_plural_variants(syn))

    return list(expanded)


def smart_phrase_matches(text_norm: str, keyword_norm: str) -> bool:
    """
    Matching inteligente para buscas SEM operadores explícitos (+ ou /).

    Lógica:
    1. Detecta grupos de sinônimos na keyword (ex.: 'placa de video' → grupo GPU)
    2. O grupo vira alternativas (OU): qualquer sinônimo serve
    3. As palavras específicas fora do grupo viram termos obrigatórios (E)

    Exemplos:
      'placa de video'        → (placa de video | gpu | vga | ...) ← genérico, qualquer GPU
      'placa de video rx 580' → (placa de video | gpu | ...) E (rx) E (580) ← específico
      'monitor gamer'         → (monitor | display | tela) E (gamer)
    """
    remaining = keyword_norm
    required_groups = []  # Lista de conjuntos alternativos (OR dentro, AND entre)

    # Detecta grupos de sinônimos dentro da keyword (longest match first)
    for group in SYNONYM_GROUPS:
        group_norm = sorted({normalize(s) for s in group}, key=len, reverse=True)
        for term in group_norm:
            if term in remaining:
                syn_variants = set()
                for syn in group_norm:
                    syn_variants.update(get_plural_variants(syn))
                required_groups.append(syn_variants)
                remaining = remaining.replace(term, '', 1).strip()
                break

    # Palavras restantes = termos específicos obrigatórios
    stopwords = {'de', 'do', 'da', 'dos', 'das', 'o', 'a', 'os', 'as', 'um', 'uma', 'e', 'em', 'no', 'na'}
    remaining_words = [w for w in remaining.split() if w and w not in stopwords and len(w) > 1]
    for word in remaining_words:
        required_groups.append(get_plural_variants(word))

    # Se não detectou nada (keyword desconhecida), faz busca direta
    if not required_groups:
        return keyword_norm in text_norm

    # Todos os grupos devem bater no texto
    for variants in required_groups:
        if not any(v in text_norm for v in variants):
            return False
    return True


def keyword_matches(offer_text: str, keyword: str) -> bool:
    """
    Verifica se o texto da oferta corresponde à palavra-chave.

    Dois modos:
    - COM operadores (+ e /): lógica explícita E/OU
    - SEM operadores: matching inteligente (detecta sinônimos + termos obrigatórios)

    Exemplos:
      'placa de video'          → qualquer GPU
      'placa de video rx 580'   → GPU específica RX 580 (não bate com RX 9060!)
      'samsung+s25'             → tem samsung E s25
      'samsung+s23/s24/s25'     → tem samsung E (s23 ou s24 ou s25)
    """
    text_norm = normalize(offer_text)
    keyword_lower = normalize(keyword)

    # Modo com operadores explícitos
    if '+' in keyword_lower or '/' in keyword_lower:
        required_groups = keyword_lower.split('+')
        for group in required_groups:
            options = [opt.strip() for opt in group.split('/') if opt.strip()]
            all_variants = []
            for opt in options:
                all_variants.extend(expand_with_synonyms(opt))
            if not any(variant in text_norm for variant in all_variants):
                return False
        return True

    # Modo inteligente (sem operadores)
    return smart_phrase_matches(text_norm, keyword_lower)


def send_alerts(offer_text: str, photo_path: str = None):
    """
    Verifica os alertas cadastrados e envia mensagem para cada usuário
    cuja palavra-chave combina com a oferta.
    """
    from bot.models import UserAlert
    import os

    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not bot_token:
        logger.warning("send_alerts: TELEGRAM_BOT_TOKEN não configurado.")
        return

    alerts = UserAlert.objects.filter(is_active=True)
    if not alerts.exists():
        return

    notified_users = set()

    for alert in alerts:
        user_id = alert.telegram_user_id
        if user_id in notified_users:
            continue

        if keyword_matches(offer_text, alert.keyword):
            notified_users.add(user_id)
            try:
                # Usa HTML para evitar erros de parse com caracteres especiais do Markdown
                from django.utils.html import escape
                safe_kw = escape(alert.keyword)
                safe_offer = escape(offer_text)

                header = (
                    f"🔔 <b>Alerta para:</b> <code>{safe_kw}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                )
                full_text = header + safe_offer

                if photo_path and os.path.exists(photo_path):
                    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                    with open(photo_path, 'rb') as img:
                        resp = http_requests.post(url, data={
                            'chat_id': user_id,
                            'caption': full_text[:1024],
                            'parse_mode': 'HTML'
                        }, files={'photo': img}, timeout=20)
                else:
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    resp = http_requests.post(url, data={
                        'chat_id': user_id,
                        'text': full_text[:4096],
                        'parse_mode': 'HTML'
                    }, timeout=10)

                if resp.status_code == 200:
                    logger.info(f"✅ Alerta enviado para {user_id} ({alert.keyword})")
                else:
                    logger.warning(f"⚠️ Erro alerta {user_id}: {resp.text[:100]}")

            except Exception as e:
                logger.error(f"❌ Erro ao enviar alerta para {user_id}: {e}")
