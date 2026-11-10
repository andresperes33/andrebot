"""Reclassifica consoles com itens inclusos (SSD/controle no título) que a
regra antiga marcava como 'controle' ou 'ssd' (ex.: 'Console PlayStation 5 Pro
Sony, SSD 2TB, Com Controle Sem Fio DualSense').

Só mexe em promoções que estão em 'controle'/'ssd' e que a regra atual
classifica como 'console'. Acessórios avulsos permanecem como estão.
"""
from django.db import migrations


def reclassificar_console_bundle(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0
    for promo in Promo.objects.filter(categoria__in=['controle', 'ssd']).iterator():
        texto = promo.texto_original or promo.titulo or ''
        if not texto:
            continue
        titulo = promo.titulo or _linha_titulo(texto)
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'console':
            continue
        promo.categoria = 'console'
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'Consoles com itens inclusos reclassificados para console: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0151_reclassificar_cupons_valor'),
    ]

    operations = [
        migrations.RunPython(reclassificar_console_bundle, migrations.RunPython.noop),
    ]
