"""Reclassifica TVs que caíram em 'caixa_som' por citar soundbar no combo.

Caso alvo: 'Samsung Smart TV 65 MiniLED 4K M75H Soundbar Samsung HW-B400F
Combo'. A regra de caixa de som retornava 'caixa_som' para qualquer texto com
a palavra 'soundbar', antes de checar os marcadores fortes de TV ('smart tv',
'televisor', 'tv 65...'). A soundbar é item incluso no combo; o produto
principal é a TV.

O classificador já foi corrigido; esta migration reaplica a classificação nas
ofertas antigas de 'caixa_som'.
"""
import re
from django.db import migrations


def reclassificar_tv(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='caixa_som').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = texto.casefold()
        if not re.search(r'\bsoundbar\b', baixa):
            continue
        if not re.search(
            r'\b(?:smart\s*tv|televis\w*|tv\s*\d{2})\b', baixa
        ):
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'tv':
            continue
        promo.categoria = 'tv'
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'TVs reclassificadas de caixa_som para tv: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0168_reclassificar_jogo_console'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_tv, migrations.RunPython.noop
        ),
    ]
