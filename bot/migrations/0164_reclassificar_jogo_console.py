"""Reclassifica jogos físicos/regionais que caíram em 'console'.

Caso alvo: 'Armored Core Vi Fires Of Rubicon físico Ps5 europa' — o
qualificador ('físico') vinha ANTES da plataforma e a região ('europa')
depois dela, então a regra de "jogo = nome + plataforma no fim" não casava
e a oferta virava 'console'. O classificador já foi corrigido; esta
migration reaplica a classificação nas ofertas antigas da categoria
'console'.
"""
import re
from django.db import migrations


def reclassificar_jogo_console(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='console').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = texto.casefold()
        if not re.search(
            r'\b(?:f[ií]sico|m[ií]dia\s*f[ií]sica|europa|asia|eua|usa|'
            r'importado|regi[aã]o|region)\b',
            baixa,
        ):
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'jogo':
            continue
        promo.categoria = 'jogo'
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'Jogos reclassificados de console para jogo: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0163_reclassificar_lista_cupons'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_jogo_console, migrations.RunPython.noop
        ),
    ]
