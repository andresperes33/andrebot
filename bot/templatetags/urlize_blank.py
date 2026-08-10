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


@register.filter(is_safe=True)
def destacar_valores(value):
    """Envolve valores (preço R$, desconto %, parcelas) em <strong>."""
    if not value:
        return ''
    texto = conditional_escape(value)
    texto = _VALOR_RE.sub(r'<strong>\1</strong>', texto)
    return mark_safe(texto)


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