import re

from django import template
from django.utils.html import mark_safe
from django.utils.html import conditional_escape

from bot.services import texto_card

register = template.Library()


# URLs seguidas de espaço, fim de linha ou símbolo (emoji colado como
# '🔗https://...'). Ignora URLs dentro de texto já linkado.
_URL_RE = re.compile(r'((?:https?|ftps?)://[^\s<>"\']+)', re.IGNORECASE)

_ATRS = ' target="_blank" rel="nofollow noopener"'


@register.filter(is_safe=True)
def urlize_blank(value):
    """Links do texto abrem em nova aba (target=_blank).

    Detecta também URLs com emoji/símbolo colado (ex.: '🔗https://...'),
    que o |urlize padrão do Django não reconhece. O texto é escapado
    antes, mantendo a proteção contra injeção HTML.
    """
    if not value:
        return ''
    texto = conditional_escape(value)
    partes = []
    pos = 0
    for m in _URL_RE.finditer(texto):
        partes.append(texto[pos:m.start()])
        url = m.group(1)
        # tira pontuação final que não faz parte da URL
        url = url.rstrip('.,;:!?\'"\u2026')
        partes.append(f'<a href="{url}"{_ATRS}>{url}</a>')
        pos = m.end()
    partes.append(texto[pos:])
    return mark_safe(''.join(partes))


@register.filter(is_safe=True)
def urlize_botao(value):
    """Converte URLs do texto em botões 'Ver oferta' do design system,
    mantendo-os na mesma posição do link original.

    Diferente do |urlize_blank (que mostra a URL em texto), aqui cada
    URL vira um botão de compra clicável (abre em nova aba).
    """
    if not value:
        return ''
    texto = conditional_escape(value)
    partes = []
    pos = 0
    for m in _URL_RE.finditer(texto):
        partes.append(texto[pos:m.start()])
        url = m.group(1)
        # tira pontuação final que não faz parte da URL
        url = url.rstrip('.,;:!?\'"\u2026')
        partes.append(
            f'<a href="{url}" target="_blank" rel="nofollow noopener" '
            f'class="btn btn-primary btn-block btn-sm" style="margin:4px 0;">'
            f'Ver oferta <i class="fas fa-arrow-right"></i></a>'
        )
        pos = m.end()
    partes.append(texto[pos:])
    return mark_safe(''.join(partes))


@register.filter
def card_text(value):
    """Texto descritivo para o card: a mensagem original até o primeiro
    link, sem cabeçalhos/notas/cupom (links já removidos)."""
    if not value:
        return ''
    return texto_card(value)


# Valores a destacar em negrito: preço em R$, percentuais de desconto
# e parcelas (ex.: R$ 96,54, 15% OFF, em até 12x).
# Usa [ \t] em vez de \s para nunca cruzar quebras de linha.
# 'x' minúsculo (parcelas) para não pegar modelos como '9600X'.
_VALOR_RE = re.compile(
    r'(R\$\s?\d[\d.,]*(?:[ \t]*-[ \t]*\d[\d.,]*)?'
    r'|\d+(?:[.,]\d+)?\s*%'
    r'|\d+x)',
)

# Mesmo padrão, mas que não casa dentro de uma tag HTML (não destaca
# atributos/URLs como 'https://...' nem quebra uma <a href="...">).
_VALOR_RE_TAG_SAFE = re.compile(
    r'(?<![=\w])(R\$\s?\d[\d.,]*(?:[ \t]*-[ \t]*\d[\d.,]*)?'
    r'|\d+(?:[.,]\d+)?\s*%'
    r'|\d+x)(?!["\'</])',
)


@register.filter(is_safe=True)
def destacar_valores(value):
    """Envolve valores (preço R$, desconto %, parcelas) em <strong> sem quebrar links."""
    if not value:
        return ''
    texto = conditional_escape(value)
    _A_OPEN = '\x00A_OPEN\x00'
    _A_CLOSE = '\x00A_CLOSE\x00'
    anchors = []
    def _guard(m):
        anchors.append(m.group(0))
        return f'{_A_OPEN}{len(anchors)-1}{_A_CLOSE}'
    texto = re.sub(r'(?is)<a\b[^>]*>.*?</a>', _guard, texto)
    texto = _VALOR_RE.sub(r'<strong>\1</strong>', texto)
    texto = re.sub(rf'{re.escape(_A_OPEN)}(\d+){re.escape(_A_CLOSE)}', lambda m: anchors[int(m.group(1))], texto)
    return mark_safe(texto)


@register.filter(is_safe=True)
def evento_html(value):
    """Processa o conteúdo do Quadro de Eventos mantendo o HTML, convertendo
    URLs em links clicáveis e destacando valores (R$, %, x).

    O autor pode colar texto com quebras de linha e emojis (ex.:
    '🔴 #AliExpress - Promoção…\\n\\nLink da Promo:\\nhttps://…\\n\\n💠 Cupons:
    R$ 12 off acima de R$ 90: BRFS1') e o evento renderiza como na imagem:
    emojis preservados, quebras de linha, link clicável e valores em negrito.
    Campo aceita HTML (conteúdo de admin confiável), então não é escapado.
    """
    if not value:
        return ''
    html = value
    # Preserva quebras de linha como <br> (conteúdo pode ser texto simples).
    html = html.replace('\n', '<br>')

    # Protege links <a ...>...</a> já existentes para não converter URLs que
    # estejam dentro de um href/texto de link já marcado (evita link duplo).
    _ANCHOR_OPEN = '\x00ANCHOR_OPEN\x00'
    _ANCHOR_CLOSE = '\x00ANCHOR_CLOSE\x00'
    anchors = []
    def _guardar(m):
        anchors.append(m.group(0))
        return f'{_ANCHOR_OPEN}{len(anchors) - 1}{_ANCHOR_CLOSE}'
    html = re.sub(r'(?is)<a\b[^>]*>.*?</a>', _guardar, html)

    # Converte URLs para links clicáveis (abrem em nova aba).
    html = _URL_RE.sub(lambda m: f'<a href="{m.group(1)}"{_ATRS}>{m.group(1)}</a>', html)

    # Destaca valores (R$, %, x) em <strong>, sem tocar em tags/URLs.
    html = _VALOR_RE_TAG_SAFE.sub(r'<strong>\1</strong>', html)

    # Restaura os links <a> previamente guardados.
    html = re.sub(rf'{_ANCHOR_OPEN}(\d+){_ANCHOR_CLOSE}', lambda m: anchors[int(m.group(1))], html)
    return mark_safe(html)


# Normaliza preços do tipo 'R$ 344' para 'R$ 344,00', 'R$ 344,9' para
# 'R$ 344,90'. Só formata números PRECEDIDOS por 'R$' (com espaço opcional),
# para nunca alterar números que não são preço (ex.: 'Ryzen 5', '3.9GHz',
# '6-Cores', '1003'). Preserva o valor original quando já tem 2 casas.
_PRECO_LIMPO_RE = re.compile(r'(R\$\s*)(\d[\d.]*(?:,\d{1,2})?)', re.IGNORECASE)


@register.filter
def preco_completo(value):
    """Garante que um preço tenha sempre 2 casas decimais (ex.: R$ 344 -> R$ 344,00)."""
    if not value:
        return value or ''

    def _fix(num):
        if ',' not in num:
            return num + ',00'
        inteiro, dec = num.rsplit(',', 1)
        if len(dec) == 1:
            return f"{inteiro},{dec}0"
        return num

    return _PRECO_LIMPO_RE.sub(lambda m: m.group(1) + _fix(m.group(2)), value)