from django.db import migrations
from bot.services import _linha_titulo, _preco_do_texto, _chave_produto
from bot.classifier import detectar_categoria, detectar_loja
import re


def reparar_promos(apps, schema_editor):
    """Recalcula título, preço, categoria, chave e loja das promoções já
    salvas a partir do texto original. Corrige registros que ficaram com
    título/preço errados por causa de teasers ('CAIU QUASE R$ 400,00!')."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        if not texto:
            continue

        titulo = _linha_titulo(texto)
        preco = _preco_do_texto(texto)
        chave = _chave_produto(promo.titulo) or _chave_produto(titulo)

        link = promo.link_afiliado or ''
        if not link:
            links = re.findall(r'(https?://\S+)', texto)
            if links:
                link = links[0].rstrip(')')
        loja = detectar_loja(link) or promo.loja
        categoria = detectar_categoria(texto, titulo=titulo) or promo.categoria

        promo.titulo = titulo or promo.titulo
        promo.preco = preco or promo.preco
        promo.produto_chave = chave or promo.produto_chave
        promo.loja = loja
        promo.categoria = categoria
        promo.save(update_fields=['titulo', 'preco', 'produto_chave', 'loja', 'categoria'])


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0030_refinar_produto_chave_tvs'),
    ]

    operations = [
        migrations.RunPython(reparar_promos, migrations.RunPython.noop),
    ]
