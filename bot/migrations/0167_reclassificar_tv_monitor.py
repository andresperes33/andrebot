"""Reclassifica TVs que caíram em 'monitor' por citar a palavra 'monitor'.

Caso alvo: 'Smart Tv Samsung 32 Hd Tizen Hdr Wi-fi Hdmi Monitor Bivolt
Preta Preto'. A regra 'Monitor tem prioridade sobre notebook' retornava
'monitor' para qualquer texto com a palavra 'monitor', antes de checar os
marcadores fortes de TV ('smart tv', 'televisor', 'tv 32...').

O classificador já foi corrigido; esta migration reaplica a classificação
nas ofertas antigas de 'monitor'.
"""
import re
from django.db import migrations


def reclassificar_tv(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='monitor').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = texto.casefold()
        if not re.search(r'\bmonitor\b', baixa):
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
        print(f'TVs reclassificadas de monitor para tv: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0166_reclassificar_booster_outros'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_tv, migrations.RunPython.noop
        ),
    ]
