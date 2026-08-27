from django.db import migrations
from bot.classifier import detectar_categoria
from bot.services import _linha_titulo


def reclassificar(apps, schema_editor):
    """Reclassifica pastas térmicas (que a regra antiga marcava como placa de
    vídeo por causa da palavra 'GPU' no texto)."""
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
        ('bot', '0035_alter_promo_categoria'),
    ]

    operations = [
        migrations.RunPython(reclassificar, migrations.RunPython.noop),
    ]
