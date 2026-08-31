from django.db import migrations
from bot.services import _linha_titulo, _chave_produto


def recalcular(apps, schema_editor):
    """Recalcula a chave de produto ignorando tempo de resposta de monitor
    ('1ms', '5ms') como medida variável — agrupa o mesmo monitor entre lojas."""
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
        ('bot', '0066_reclassificar_cupons_outros'),
    ]

    operations = [
        migrations.RunPython(recalcular, noop),
    ]
