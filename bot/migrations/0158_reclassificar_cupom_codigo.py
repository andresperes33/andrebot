"""Reclassifica cupons salvos como 'outros' por causa da linha do código.

Caso alvo: mensagens com 'Código: 20D3SBL0QU34D0' (ex.: '‼️ CUPOM SHOPEE').
A linha do código era tratada como nome de produto (heurística de modelo
letra+dígito), então a postagem parecia produto e caía em 'outros' — e o
título do card virava o próprio código.

Esta migration roda o classificador já corrigido sobre as ofertas salvas.
"""
from django.db import migrations


def reclassificar_cupom_codigo(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _eh_anuncio_cupom, _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0
    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        if 'cupom' not in texto.casefold() and 'cupons' not in texto.casefold():
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
        if titulo and _eh_anuncio_cupom(titulo) and promo.titulo != titulo:
            promo.titulo = titulo[:250]
            update_fields.append('titulo')
        promo.save(update_fields=update_fields)
        n += 1

    if n:
        print(f'Cupons com codigo reclassificados de outros para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0157_reclassificar_console_controle_corpo'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_cupom_codigo, migrations.RunPython.noop
        ),
    ]
