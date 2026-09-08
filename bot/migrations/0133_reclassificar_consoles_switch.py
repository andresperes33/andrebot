from django.db import migrations
import re


def reclassificar(apps, schema_editor):
    """Corrige consoles (ex.: 'Nintendo Switch Console OLED 64gb') que foram
    marcados como 'tv' porque a regra de TV pegava 'OLED' no título."""
    Promo = apps.get_model('bot', 'Promo')
    padrao_console = re.compile(
        r'(?:\bnintendo\s*switch\b'
        r'|\bswitch\b(?=\s*(?:nintendo|oled|lite|2\b|\d|joy|v2))'
        r'|\bplaystation\b'
        r'|\bxbox\b'
        r'|\bsteam\s*deck\b'
        r'|\bok\s*1\b'
        r'|\bhandheld\b)',
        re.IGNORECASE,
    )
    for promo in Promo.objects.filter(categoria='tv').iterator():
        texto = promo.texto_original or promo.titulo or ''
        titulo = promo.titulo or ''
        if padrao_console.search(f'{titulo} {texto}'):
            promo.categoria = 'console'
            promo.save(update_fields=['categoria'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0132_reclassificar_caixa_som_microfone'),
    ]

    operations = [
        migrations.RunPython(reclassificar, noop),
    ]