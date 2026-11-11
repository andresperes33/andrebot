"""Reclassifica anúncios de cupom 'Próximo/Último Cupom ...' salvos como 'outros'.

Caso alvo: títulos como 'Próximo Cupom 35 OFF Mercado Livre APP', que a regra
antiga não reconhecia como anúncio de cupom (só aceitava prefixo 'novo/nova')
e por isso caíam em 'outros'.
"""
from django.db import migrations


def reclassificar_cupom_proximo(apps, schema_editor):
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
        print(f'Cupons "Proximo/Ultimo Cupom" reclassificados para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0153_alter_promo_categoria'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_cupom_proximo, migrations.RunPython.noop
        ),
    ]
