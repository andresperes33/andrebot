from django.db import migrations
from bot.classifier import detectar_categoria
from bot.services import _linha_titulo, _chave_produto


def reclassificar(apps, schema_editor):
    """Reclassifica placas-mãe com soquete/processador no texto (ex.: 'MSI
    Placa-mãe ... Intel Core Ultra') que a regra antiga marcava como notebook,
    e recalcula a chave (ignora variação de soquete lga1851/1851)."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        titulo = _linha_titulo(texto)
        nova = detectar_categoria(texto, titulo=titulo)
        chave = _chave_produto(promo.titulo) or _chave_produto(titulo)
        if nova and nova != promo.categoria:
            promo.categoria = nova
            promo.save(update_fields=['categoria'])
        if chave and chave != promo.produto_chave:
            promo.produto_chave = chave
            promo.save(update_fields=['produto_chave'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0057_recalcular_chave_sufixos_gpu'),
    ]

    operations = [
        migrations.RunPython(reclassificar, noop),
    ]
