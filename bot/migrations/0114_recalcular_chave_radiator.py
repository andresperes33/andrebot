from django.db import migrations
from bot.services import _chave_produto, _linha_titulo


def recalcular(apps, schema_editor):
    """Recalcula a chave do produto. Corrige water coolers: antes o '360' (do
    radiador) virava 'código de modelo' e o histórico agrupava water coolers
    de marcas diferentes (Gigabyte GME 360, Corsair H150i, Cooler Master)."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        titulo = _linha_titulo(texto) or promo.titulo
        chave = _chave_produto(titulo) or _chave_produto(promo.titulo)
        if chave and chave != promo.produto_chave:
            promo.produto_chave = chave
            promo.save(update_fields=['produto_chave'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0113_reclassificar_pasta_termica'),
    ]

    operations = [
        migrations.RunPython(recalcular, noop),
    ]
