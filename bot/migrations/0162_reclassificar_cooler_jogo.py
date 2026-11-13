"""Reclassifica dois casos que caíam na categoria errada.

1. 'Placa-mãe' como rótulo com hífen não era reconhecido como linha de
   categoria, então 'CPU cooler ... ótimo para X99' virava 'placa_mae'
   (o X99 é só o chipset compatível). Agora é 'cooler'.
2. Jogo vendido com edição + plataforma + 'Físico'
   ('Ghost of Yotei Complete Edition PlayStation 5 PS5 Físico') caía em
   'console'. Agora é 'jogo'.

O classificador já foi corrigido; esta migration reaplica a classificação
nas ofertas antigas, limitando-se às categorias afetadas.
"""
from django.db import migrations


def reclassificar_cooler_jogo(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n_cooler = 0
    n_jogo = 0

    for promo in Promo.objects.filter(categoria='placa_mae').iterator():
        texto = promo.texto_original or promo.titulo or ''
        if 'cooler' not in texto.casefold():
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'cooler':
            continue
        promo.categoria = 'cooler'
        promo.save(update_fields=['categoria'])
        n_cooler += 1

    for promo in Promo.objects.filter(categoria='console').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = texto.casefold()
        if not any(
            termo in baixa
            for termo in ('edition', 'collection', 'físico', 'fisico')
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
        n_jogo += 1

    if n_cooler:
        print(f'Coolers reclassificados de placa_mae para cooler: {n_cooler}')
    if n_jogo:
        print(f'Jogos reclassificados de console para jogo: {n_jogo}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0161_reclassificar_cupom_desconto'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_cooler_jogo, migrations.RunPython.noop
        ),
    ]
