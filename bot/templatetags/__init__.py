from django import template
from django.utils.html import urlize as _urlize

register = template.Library()


@register.filter(is_safe=True)
def urlize_blank(value):
    """Igual ao |urlize, mas links abrem em nova aba (target=_blank)."""
    return _urlize(value, autoescape=True).replace(
        '<a href="', '<a href=" target="_blank" rel="nofollow noopener"'
    )