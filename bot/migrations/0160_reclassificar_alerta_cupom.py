"""Reclassifica alertas de cupom salvos como 'outros'.

Caso alvo: 'ALERTA de Cupom Kabum!' com a linha 'valido em notebooks
selecionados'. O termo 'notebooks' fazia a linha parecer nome de produto,
então a postagem deixava de ser reconhecida como anúncio de cupom e caía em
'outros'. O classificador já foi corrigido; esta migration reaplica a
classificação nas ofertas antigas.
"""
from django.db import migrations


def reclassificar_alerta_cupom(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0
    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        if 'alerta de cupom' not in texto.casefold():
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'cupom':
            continue
        promo.categoria = 'cupom'
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'Alertas de cupom reclassificados de outros para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0159_reclassificar_ram_jogo'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_alerta_cupom, migrations.RunPython.noop
        ),
    ]
