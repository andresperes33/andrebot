from django.db import migrations
from bot.classifier import detectar_categoria
from bot.services import _linha_titulo


def reclassificar(apps, schema_editor):
    """Reclassifica extensões elétricas/rebuas de tomadas que a regra antiga
    marcava como 'Notebook'."""
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
        ('bot', '0098_corrigir_titulo_valor'),
    ]

    operations = [
        migrations.RunPython(reclassificar, noop),
    ]
