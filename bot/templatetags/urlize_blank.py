from django import template
from django.utils.html import urlize as _urlize, mark_safe
from django.utils.safestring import SafeString

register = template.Library()


@register.filter(is_safe=True)
def urlize_blank(value):
    """Igual ao |urlize, mas links abrem em nova aba (target=_blank)."""
    html = _urlize(value, autoescape=True)
    # urlize com autoescape devolve a string escapada, porém SafeString
    # (ex.: <a href="..."> vira &lt;a href=&quot;...&quot;&gt;).
    novo = html.replace('<a href="', '<a href=" target="_blank" rel="nofollow noopener"')
    if novo == html:
        novo = html.replace('&lt;a href=&quot;', '&lt;a href=&quot; target=&quot;_blank&quot; rel=&quot;nofollow noopener&quot;')
    return mark_safe(novo)