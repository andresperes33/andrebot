from django.db import migrations
from bot.classifier import detectar_categoria
from bot.services import _linha_titulo


def reclassificar(apps, schema_editor):
    """Reclassifica kits de fans (que apareciam como 'celular' por causa de
    'Galaxy' ou como 'kit' por causa de 'Kit 3 fans')."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        titulo = _linha_titulo(texto)
        nova = detectar_categoria(texto, titulo=titulo)
        if nova and nova != promo.categoria:
            promo.categoria = nova
            promo.save(update_fields=['categoria'])


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0036_reclassificar_pasta_termica'),
    ]

    operations = [
        migrations.RunPython(reclassificar, migrations.RunPython.noop),
    ]
