import re
from django.db import migrations


def _normalizar_url(url):
    url = (url or '').strip().rstrip('.,;|)')
    url = re.split(r'[?#]', url)[0]
    url = re.sub(r'^https?://', '', url, flags=re.I)
    url = re.sub(r'^www\.', '', url, flags=re.I)
    url = url.rstrip('/')
    return url.lower()


def _primeiro_link_produto(texto):
    for lnk in re.findall(r'(https?://\S+)', texto or ''):
        lnk = lnk.rstrip('.,;|)')
        if any(d in lnk for d in ['t.me/', 'linktr.ee', 'youtube', 'youtu.be', 'tecnan.com.br', 'links.andreindica']):
            continue
        return lnk
    return ''


def backfill_produto_chave(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.filter(produto_chave='').iterator():
        chave = _normalizar_url(_primeiro_link_produto(promo.texto_original))
        if not chave:
            chave = _normalizar_url(promo.link_afiliado)
        if chave:
            produto_chave = chave
            # Preserva a URL completa (com preço) no url_chave, como está.
            # O produto_chave NÃO recebe o preço: identifica o mesmo produto
            # independente do valor.
            promo.produto_chave = produto_chave
            promo.save(update_fields=['produto_chave'])


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0023_promo_produto_chave'),
    ]

    operations = [
        migrations.RunPython(backfill_produto_chave, migrations.RunPython.noop),
    ]
