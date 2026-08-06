import re

from django import template
from django.utils.html import urlize as _urlize, mark_safe

register = template.Library()


@register.filter(is_safe=True)
def urlize_blank(value):
    """Igual ao |urlize, mas links abrem em nova aba (target=_blank)."""
    html = _urlize(value, autoescape=True)
    # Insere o atributo alvo/referrer depois do href, sem quebrar a URL.
    novo = re.sub(
        r'<a href="([^"]+)"',
        r'<a href="\1" target="_blank" rel="nofollow noopener"',
        html,
    )
    return mark_safe(novo)