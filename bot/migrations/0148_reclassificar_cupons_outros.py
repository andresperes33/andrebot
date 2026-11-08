"""Reclassifica promoções de cupom que foram salvas como 'outros'."""
from django.db import migrations


def reclassificar_cupons_outros(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _eh_anuncio_cupom, _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0
    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        if 'cupom' not in texto.casefold() and 'cupons' not in texto.casefold():
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'cupom':
            continue
        promo.categoria = 'cupom'
        update_fields = ['categoria']
        if titulo and _eh_anuncio_cupom(titulo) and promo.titulo != titulo:
            promo.titulo = titulo[:250]
            update_fields.append('titulo')
        promo.save(update_fields=update_fields)
        n += 1

    if n:
        print(f'Cupons reclassificados de outros para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0147_reclassificar_bomba_ar'),
    ]

    operations = [
        migrations.RunPython(reclassificar_cupons_outros, migrations.RunPython.noop),
    ]
