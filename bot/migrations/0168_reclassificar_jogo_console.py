"""Reclassifica jogos que caíram em 'console' por citar a plataforma.

Caso alvo: '45% OFF Games Prime Exclusive' com o produto
'Marvel's Spider-Man: Miles Morales - PlayStation 4 - R$ 67,00' no corpo.
A primeira linha é só um cabeçalho de desconto, então a regra que reconhece
'nome do jogo + plataforma' não era aplicada e a plataforma citada no corpo
fazia a oferta virar 'console'.

O classificador já foi corrigido; esta migration reaplica a classificação
nas ofertas antigas de 'console'.
"""
import re
from django.db import migrations


def reclassificar_jogo(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='console').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = texto.casefold()
        if not re.search(
            r'\b(?:playstation|ps\s?[1-5]|xbox|nintendo|switch)\b', baixa
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
        ('bot', '0167_reclassificar_tv_monitor'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_jogo, migrations.RunPython.noop
        ),
    ]
