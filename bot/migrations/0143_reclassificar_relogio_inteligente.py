"""Reclassifica smartwatches/relógios inteligentes que a regra antiga marcava
como 'notebook'/'outros' (ex.: 'Amazfit Bip 5 ... Relógio inteligente tela de
1,91 polegadas' — a 'tela ... polegadas' era confundida com notebook)."""
from django.db import migrations

_CHAVES_SMARTWATCH = (
    'relógio inteligente', 'relogio inteligente',
    'smartwatch', 'smart watch',
    'apple watch', 'galaxy watch',
    'amazfit', 'smartband', 'fitness band',
)


def reclassificar_relogio(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    total = 0
    for chave in _CHAVES_SMARTWATCH:
        qs = Promo.objects.filter(
            categoria__in=['notebook', 'outros', 'celular', 'tablet'],
        ).filter(
            titulo__icontains=chave,
        )
        n = qs.update(categoria='relogio_inteligente')
        total += n
    if total:
        print(f'Relógios inteligentes reclassificados -> relogio_inteligente: {total}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0142_alter_promo_categoria'),
    ]

    operations = [
        migrations.RunPython(reclassificar_relogio, migrations.RunPython.noop),
    ]