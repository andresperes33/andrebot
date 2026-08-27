from django.db import migrations
from bot.services import _linha_titulo, _chave_produto


def recalcular(apps, schema_editor):
    """Recalcula a chave de produto com a normalização corrigida:
    descritores comuns (microfone/lapela/versão/tipo-c) removidos e tokens
    ordenados para agrupar o mesmo produto entre lojas/textos diferentes."""
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
        ('bot', '0050_recalcular_chave_medidas'),
    ]

    operations = [
        migrations.RunPython(recalcular, noop),
    ]
