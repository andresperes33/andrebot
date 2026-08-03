from django.db import migrations
from bot.classifier import detectar_categoria


def reclassificar_promos(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        nova = detectar_categoria(promo.texto_original or promo.titulo)
        if nova and nova != promo.categoria:
            promo.categoria = nova
            promo.save(update_fields=['categoria'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0009_alter_promo_categoria'),
    ]

    operations = [
        migrations.RunPython(reclassificar_promos, noop),
    ]
