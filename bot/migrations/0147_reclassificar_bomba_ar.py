"""Reclassifica produtos de bomba de ar/compressor que caíram em 'cupom'.

A linha 'Cupom: CODIGO' fazia o classificador tratar o anúncio como cupom
quando o título do produto não tinha um termo reconhecido em _TERMOS_PRODUTO
(ex.: 'Baseus bomba de ar ...'). Agora 'bomba', 'compressor', 'inflador' etc.
são reconhecidos como produto, então a categoria correta é recalculada.
"""
from django.db import migrations
from django.db.models import Q


def reclassificar(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    qs = Promo.objects.filter(categoria='cupom').filter(
        Q(titulo__icontains='bomba')
        | Q(titulo__icontains='compressor')
        | Q(titulo__icontains='inflador')
        | Q(texto_original__icontains='bomba de ar')
        | Q(texto_original__icontains='compressor de ar')
    )

    alteradas = 0
    for promo in qs.iterator():
        texto = promo.texto_original or promo.titulo
        if not texto:
            continue
        titulo = _linha_titulo(texto)
        nova = detectar_categoria(texto, titulo=titulo)
        if nova and nova != promo.categoria:
            promo.categoria = nova
            promo.save(update_fields=['categoria'])
            alteradas += 1

    if alteradas:
        print(f'Reclassificadas {alteradas} promocoes de bomba/compressor.')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0146_preencher_lojas_vazias'),
    ]

    operations = [
        migrations.RunPython(reclassificar, migrations.RunPython.noop),
    ]
