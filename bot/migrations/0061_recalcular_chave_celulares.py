from django.db import migrations
from bot.services import _linha_titulo, _chave_produto


def recalcular(apps, schema_editor):
    """Recalcula a chave de produto: megapixels ('50mp') e descritores de
    celular não entram mais na chave; modelos como a17/g17/edge70/edge50 são
    separados corretamente (Galaxy A17 ≠ G17 ≠ Edge 70)."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        titulo = _linha_titulo(promo.texto_original or promo.titulo)
        chave = _chave_produto(promo.titulo) or _chave_produto(titulo)
        if chave and chave != promo.produto_chave:
            promo.produto_chave = chave
            promo.save(update_fields=['produto_chave'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0060_reclassificar_motorola'),
    ]

    operations = [
        migrations.RunPython(recalcular, noop),
    ]
