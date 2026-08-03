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


def backfill_url_chave(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.filter(url_chave='').iterator():
        chave = _normalizar_url(_primeiro_link_produto(promo.texto_original))
        if not chave:
            chave = _normalizar_url(promo.link_afiliado)
        if chave:
            # Evita colisão de chave com outra promo já existente
            ja_existe = Promo.objects.filter(url_chave=chave).exclude(pk=promo.pk).exists()
            if ja_existe:
                promo.delete()
            else:
                promo.url_chave = chave
                promo.save(update_fields=['url_chave'])


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0007_promo_url_chave'),
    ]

    operations = [
        migrations.RunPython(backfill_url_chave, migrations.RunPython.noop),
    ]
