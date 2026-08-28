from django.db import migrations
from bot.services import _linha_titulo, _chave_produto


def recalcular(apps, schema_editor):
    """Recalcula a chave de produto separando modelos com sufixo
    ('5060 ti' -> '5060ti', '4070 super' -> '4070super') e tratando
    memória (gddr7) e números de modelo de GPU (5060) corretamente."""
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
        ('bot', '0056_reclassificar_acessorios_notebook'),
    ]

    operations = [
        migrations.RunPython(recalcular, noop),
    ]
