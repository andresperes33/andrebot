import re

from django import template
from django.utils.html import mark_safe
from django.utils.html import conditional_escape

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