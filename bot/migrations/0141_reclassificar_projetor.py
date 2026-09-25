"""Reclassifica projetores que a regra antiga marcava como 'console'
(ex.: 'Projetor HY300 ... Xbox PS5' — os consoles são só compatibilidade)."""
from django.db import migrations


def reclassificar_projetor(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    qs = Promo.objects.filter(categoria='console').filter(
        titulo__icontains='projetor'
    )
    n = qs.update(categoria='outros')
    if n:
        print(f'Projetores reclassificados de console -> outros: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0140_remover_blog'),
    ]

    operations = [
        migrations.RunPython(reclassificar_projetor, migrations.RunPython.noop),
    ]
