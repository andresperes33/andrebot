from django.db import migrations
from bot.services import _link_produto_compra
from bot.classifier import detectar_loja


def corrigir(apps, schema_editor):
    """Corrige o link_afiliado das promoções: o botão de compra deve apontar
    para o link do PRODUTO (e não o do cupom), quando ambos aparecem."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        novo_link = _link_produto_compra(texto)
        if novo_link and novo_link != promo.link_afiliado:
            novo_loja = detectar_loja(novo_link) or promo.loja
            promo.link_afiliado = novo_link
            promo.loja = novo_loja
            promo.save(update_fields=['link_afiliado', 'loja'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0105_reclassificar_tvs_marca'),
    ]

    operations = [
        migrations.RunPython(corrigir, noop),
    ]
