from django.db import migrations
from bot.services import _linha_titulo, _chave_produto


def reclassificar(apps, schema_editor):
    """Corrige título e chave de promoções cuja linha 'N Pç no estoque'
    era usada como título (ignora linhas de quantidade/estoque)."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        titulo = _linha_titulo(texto) or promo.titulo
        chave = _chave_produto(titulo) or _chave_produto(promo.titulo)
        if titulo and titulo != promo.titulo:
            promo.titulo = titulo
            promo.save(update_fields=['titulo'])
        if chave and chave != promo.produto_chave:
            promo.produto_chave = chave
            promo.save(update_fields=['produto_chave'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0063_reclassificar_air_coolers'),
    ]

    operations = [
        migrations.RunPython(reclassificar, noop),
    ]
