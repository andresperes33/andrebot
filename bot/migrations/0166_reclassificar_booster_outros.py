"""Reclassifica cartas colecionáveis (display + booster) para 'outros'.

Caso alvo: 'Reinado Delta Box Display 36 Booster, R$ 9,43 por booster'.
O termo 'display' fazia a oferta cair em 'monitor' e, quando o texto citava
um cupom, em 'cupom'. Agora 'display ... booster', 'booster ... display',
'booster box' e 'box de boosters' são reconhecidos como cartas colecionáveis
('outros').

O classificador já foi corrigido; esta migration reaplica a classificação
nas ofertas antigas.
"""
import re
from django.db import migrations


def reclassificar_booster(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.exclude(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = texto.casefold()
        if not re.search(r'\bboosters?\b', baixa):
            continue
        if not re.search(r'\bdisplay\b|\bbox\b', baixa):
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'outros':
            continue
        promo.categoria = 'outros'
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'Cartas colecionaveis reclassificadas para outros: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0165_reclassificar_monitor'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_booster, migrations.RunPython.noop
        ),
    ]
