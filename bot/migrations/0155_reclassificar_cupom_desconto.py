"""Reclassifica anúncios de desconto/cupom sem a palavra 'cupom' salvos como 'outros'.

Caso alvo: '50% OFF Shopee x Nubank RENOVADO!', que é um cupom/desconto de
parceria (loja x banco) mas a regra antiga só reconhecia anúncios com a
palavra 'cupom' e por isso caía em 'outros'. Também corrige o título, que
perdia o '%' ('50 OFF ...' -> '50% OFF ...').
"""
from django.db import migrations


def reclassificar_cupom_desconto(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0
    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        if not texto:
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
        if titulo and promo.titulo != titulo:
            promo.titulo = titulo[:250]
            update_fields.append('titulo')
        promo.save(update_fields=update_fields)
        n += 1

    if n:
        print(f'Cupons de desconto (loja/banco) reclassificados para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0154_reclassificar_cupom_proximo'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_cupom_desconto, migrations.RunPython.noop
        ),
    ]
