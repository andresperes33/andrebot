from django.db import migrations
from bot.services import _chave_produto, _linha_titulo, _preco_do_texto
from bot.classifier import detectar_categoria


def recalcular(apps, schema_editor):
    """Recalcula a chave do produto e a categoria das promoções. Corrige o
    histórico de preços de monitores (e afins): antes das specs do painel
    ('144hz,', 'hdr10,') entrarem na chave como 'código de modelo', a chave
    variava entre postagens e o histórico de preços não agrupava o produto."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        titulo = _linha_titulo(texto) or promo.titulo
        chave = _chave_produto(titulo) or _chave_produto(promo.titulo)
        atualizar = []
        if chave and chave != promo.produto_chave:
            promo.produto_chave = chave
            atualizar.append('produto_chave')
        nova = detectar_categoria(texto, titulo=titulo)
        if nova and nova != promo.categoria:
            promo.categoria = nova
            atualizar.append('categoria')
        preco = _preco_do_texto(texto)
        if preco and preco != promo.preco:
            promo.preco = preco
            atualizar.append('preco')
        if atualizar:
            promo.save(update_fields=atualizar)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0095_alter_promo_categoria'),
    ]

    operations = [
        migrations.RunPython(recalcular, noop),
    ]
