from django.db import migrations
from bot.classifier import detectar_categoria
from bot.services import _linha_titulo, _chave_produto, _preco_do_texto


def reclassificar(apps, schema_editor):
    """Corrige título/categoria de anúncios que começam com linhas de
    contextualização como 'Ativou para quem resgatou ontem' e trazem
    'NOVO Cupom Mercado Livre' na sequência."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        titulo = _linha_titulo(texto)
        if not titulo:
            continue
        nova = detectar_categoria(texto, titulo=titulo)
        atualizar = []
        if nova and nova != promo.categoria:
            promo.categoria = nova
            atualizar.append('categoria')
        if titulo != promo.titulo:
            promo.titulo = titulo
            atualizar.append('titulo')
        chave = _chave_produto(titulo) or _chave_produto(promo.titulo)
        if chave and chave != promo.produto_chave:
            promo.produto_chave = chave
            atualizar.append('produto_chave')
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
        ('bot', '0086_reclassificar_cupons_prioridade'),
    ]

    operations = [
        migrations.RunPython(reclassificar, noop),
    ]
