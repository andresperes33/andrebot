from django.db import migrations
from bot.services import _linha_titulo, _chave_produto, _preco_do_texto
from bot.classifier import detectar_categoria


def corrigir(apps, schema_editor):
    """Corrige os títulos de promos que ficaram como 'Valor R$ 4.837,09'.
    A linha de rótulo de preço era escolhida como título, em vez do nome real
    do produto ('iPhone 17 ... com Nota Fiscal')."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        titulo = _linha_titulo(texto)
        if not titulo:
            continue
        atualizar = []
        if titulo != promo.titulo:
            promo.titulo = titulo
            atualizar.append('titulo')
        chave = _chave_produto(titulo) or _chave_produto(promo.titulo)
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
        ('bot', '0097_reclassificar_produtos_cupom'),
    ]

    operations = [
        migrations.RunPython(corrigir, noop),
    ]
