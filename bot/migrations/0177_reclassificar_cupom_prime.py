"""Reclassifica cupons cujo título foi tomado pela chamada 'Torne-se Prime'.

Caso alvo:
    🔥 Cupom Amazon
    Só no app - R$ 250,00 OFF em Samsung: SAMSUNG250
    Resgate aqui
    Torne-se Prime 30 dias de teste Grátis

A linha do Prime virava o título do card e a categoria caía em 'outros'.
O classificador já foi corrigido; esta migration reaplica em ofertas antigas.
"""
from django.db import migrations


def reclassificar_cupons_prime(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = texto.casefold()
        if 'cupom' not in baixa:
            continue
        if not any(marc in baixa for marc in (
            'prime', '30 dias', 'teste gratis', 'teste grátis',
        )):
            continue

        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'cupom':
            continue

        promo.categoria = 'cupom'
        update_fields = ['categoria']
        if titulo and promo.titulo != titulo:
            promo.titulo = titulo[:250]
            update_fields.append('titulo')
        promo.save(update_fields=update_fields)
        n += 1

    if n:
        print(f'Cupons com chamada Prime reclassificados: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0176_reclassificar_cupom_amazon_valor'),
    ]

    operations = [
        migrations.RunPython(reclassificar_cupons_prime, migrations.RunPython.noop),
    ]
