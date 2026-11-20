"""Reclassifica bundles de console que estavam como 'jogo'.

Caso alvo:
    📢 Bundle Nintendo Switch 2 + EA Sports FC 27
    De R$ 4.699,00 por R$ 3.657,00 no Pix

O título começava com 'Bundle' e a plataforma vinha depois, então a regra
de jogo avulso ganhava. O classificador já foi corrigido; esta migration
reaplica a categoria nas ofertas antigas.
"""
from django.db import migrations


def reclassificar_bundles_console(apps, schema_editor):
    from bot.classifier import detectar_categoria

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='jogo').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = texto.casefold()
        if not any(marc in baixa for marc in (
            'bundle', 'pacote', 'com jogos', 'jogo incluso', 'edicao com',
        )):
            continue
        if not any(marc in baixa for marc in (
            'playstation', 'ps2', 'ps3', 'ps4', 'ps5',
            'xbox', 'nintendo', 'switch', 'console',
        )):
            continue
        try:
            correta = detectar_categoria(texto, titulo=promo.titulo)
        except Exception:
            continue
        if correta != 'console':
            continue
        promo.categoria = 'console'
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'Bundles de console reclassificados de jogo para console: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0177_reclassificar_cupom_prime'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_bundles_console, migrations.RunPython.noop
        ),
    ]
