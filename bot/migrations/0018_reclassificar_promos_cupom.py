from django.db import migrations
from bot.classifier import detectar_categoria
from bot.services import _linha_titulo


def reclassificar_promos(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        titulo = _linha_titulo(promo.texto_original or promo.titulo)
        nova = detectar_categoria(promo.texto_original or promo.titulo, titulo=titulo)
        if nova and nova != promo.categoria:
            promo.categoria = nova
            promo.save(update_fields=['categoria'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0017_promo_produto_chave'),
    ]

    operations = [
        migrations.RunPython(reclassificar_promos, noop),
    ]
