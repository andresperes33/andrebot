"""Reclassifica monitores que caíram em 'outros'.

Caso alvo: 'Samsung Odyssey G5 2.7 Qhd 180 Hz, 0,03 ms, G-sync Freesync'.
O título não tem a palavra 'monitor' e a regra só reconhecia algumas taxas
de atualização (144/165/240/280/360Hz, sem espaço antes de 'hz'). Agora QHD,
180Hz (com ou sem espaço) e G-Sync/FreeSync identificam monitor.

O classificador já foi corrigido; esta migration reaplica a classificação
nas ofertas antigas de 'outros'.
"""
import re
from django.db import migrations


def reclassificar_monitor(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = texto.casefold()
        if not re.search(
            r'\b(?:qhd|wqhd|1440p|freesync|g-?sync|\d{2,3}\s*hz)\b',
            baixa,
        ):
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'monitor':
            continue
        promo.categoria = 'monitor'
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'Monitores reclassificados de outros para monitor: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0164_reclassificar_jogo_console'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_monitor, migrations.RunPython.noop
        ),
    ]
