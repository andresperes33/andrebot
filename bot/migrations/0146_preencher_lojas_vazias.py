"""Preenche a loja de promoções antigas que ficaram sem loja.

Alguns links de afiliado usam domínios curtos (s.click.ali, amzn.to, meli.la,
mgl.io, tidd.ly) que não eram reconhecidos por detectar_loja. A loja ficava
vazia e o site exibia "Loja". Aqui preenchemos apenas as promoções vazias.
"""
from django.db import migrations


def preencher_lojas(apps, schema_editor):
    from bot.classifier import detectar_loja

    Promo = apps.get_model('bot', 'Promo')
    n = 0
    for promo in Promo.objects.filter(loja='').iterator():
        loja = detectar_loja(promo.link_afiliado)
        if not loja:
            loja = detectar_loja(promo.texto_original or promo.titulo or '')
        if not loja:
            continue
        promo.loja = loja
        promo.save(update_fields=['loja'])
        n += 1

    if n:
        print(f'Lojas preenchidas em promoções antigas: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0145_reverter_cupom_ml'),
    ]

    operations = [
        migrations.RunPython(preencher_lojas, migrations.RunPython.noop),
    ]
