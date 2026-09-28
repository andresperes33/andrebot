"""Reverte a 0144: reclassifica de volta as promoções que foram marcadas como
cupom ML indevidamente (ex.: produto com cupom + Mercado Livre). Usa o
classificador atual para decidir a categoria correta e restaura a loja.

Versão RÁPIDA: não baixa imagens (evita travar o deploy). A imagem de cupom
que ficou em promoções não-cupom pode ser corrigida depois por um comando."""
from django.db import migrations


def reverter_cupom_ml(apps, schema_editor):
    from bot.classifier import detectar_categoria, detectar_loja
    from bot.services import _linha_titulo
    Promo = apps.get_model('bot', 'Promo')

    # Promos que a 0144 tocou: cupom + loja ML + imagem 'cupom_ml_'
    qs = Promo.objects.filter(
        categoria='cupom',
        loja='Mercado Livre',
        imagem_url__contains='cupom_ml_',
    )
    n = 0
    for promo in qs.iterator():
        texto = promo.texto_original or promo.titulo or ''
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if not correta or correta == 'cupom':
            continue  # é cupom mesmo — mantém

        promo.categoria = correta
        promo.loja = detectar_loja(promo.link_afiliado)
        promo.save(update_fields=['categoria', 'loja'])
        n += 1

    if n:
        print(f'Promoções revertidas (não eram cupom): {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0144_reclassificar_cupom_ml'),
    ]

    operations = [
        migrations.RunPython(reverter_cupom_ml, migrations.RunPython.noop),
    ]