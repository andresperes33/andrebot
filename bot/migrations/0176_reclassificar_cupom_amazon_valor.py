"""Reclassifica cupons Amazon com valor/condição de 'outros' para 'cupom'.

Caso alvo:
    ❕ Cupom Amazon

    R$ 100,00 em compras acima de R$ 999,00: 100BLACKOFF

    Resgate aqui.

A linha de valor/condição era confundida com nome de produto, então o título
do card virava 'R 100,00 em compras acima de R 999,00 100BLACKOFF' e a
categoria caía em 'outros'.

O classificador já foi corrigido; esta migration reaplica a classificação
nas ofertas antigas de 'outros' que seguem esse padrão.
"""
from django.db import migrations


def reclassificar_cupons_amazon_valor(apps, schema_editor):
    from bot.classifier import _limpar_compat, _norm, detectar_categoria
    from bot.services import _eh_linha_valor_cupom, _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        if 'cupom' not in texto.casefold():
            continue

        linhas = [
            _norm(_limpar_compat(linha))
            for linha in texto.split('\n')
        ]
        if not any(_eh_linha_valor_cupom(linha) for linha in linhas if linha):
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
        print(f'Cupons com valor/condicao reclassificados de outros para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0175_reclassificar_anuncio_app_missoes'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_cupons_amazon_valor, migrations.RunPython.noop
        ),
    ]
