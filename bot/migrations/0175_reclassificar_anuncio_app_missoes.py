"""Reclassifica anúncios de missões/créditos do app de 'outros' para 'cupom'.

Caso alvo: '(APP) Faça Missões no Aliexpress e troque por créditos de compra!!'.
É uma promoção de app/cupom, sem produto, mas caía em 'outros' porque não
cita código, percentual de desconto nem a palavra 'cupom'.

O classificador já foi corrigido; esta migration reaplica a classificação
nas ofertas antigas de 'outros' que se encaixam no padrão.
"""
from django.db import migrations


def reclassificar_anuncios_app(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _eh_anuncio_app_missoes

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        if not _eh_anuncio_app_missoes(texto):
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
        print(f'Anuncios de app reclassificados de outros para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0174_reclassificar_alerta_ofertas'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_anuncios_app, migrations.RunPython.noop
        ),
    ]
