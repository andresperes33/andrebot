"""Reclassifica avisos de ofertas (sem produto) de 'outros' para 'cupom'.

Caso alvo: 'ALERTA de Novas Ofertas Black Friday Amazon!' + 'Começa hoje
meia noite!!'. É um aviso de ofertas/cupons, não um produto — mas caía em
'outros' porque não cita código nem a palavra 'cupom'.

O classificador já foi corrigido; esta migration reaplica a classificação
nas ofertas antigas de 'outros' que são avisos de ofertas.
"""
from django.db import migrations


def reclassificar_alertas_ofertas(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _eh_anuncio_alerta_ofertas

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        if not _eh_anuncio_alerta_ofertas(texto):
            continue
        try:
            correta = detectar_categoria(texto, titulo=promo.titulo)
        except Exception:
            continue
        if correta != 'cupom':
            continue
        promo.categoria = 'cupom'
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'Avisos de ofertas reclassificados de outros para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0173_atualizar_tag_amazon'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_alertas_ofertas, migrations.RunPython.noop
        ),
    ]
