from django.db import migrations
from bot.classifier import detectar_categoria
from bot.services import _linha_titulo


def reclassificar(apps, schema_editor):
    """Reclassifica placas-mãe com 'DDR'/'Quad Channel' no texto
    (ex.: 'MACHINIST X99 K9 DDR3 Chipset C612') que a regra antiga
    marcava como memória RAM."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        titulo = _linha_titulo(texto)
        nova = detectar_categoria(texto, titulo=titulo)
        if nova and nova != promo.categoria:
            promo.categoria = nova
            promo.save(update_fields=['categoria'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0072_reclassificar_ssd_console'),
    ]

    operations = [
        migrations.RunPython(reclassificar, noop),
    ]
