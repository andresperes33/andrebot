"""Reclassifica anúncios de roleta no app de 'outros' para 'cupom'.

Caso alvo:
    👀 (APP) Roleta na Amazon - Contas Selecionadas
    - Abra o o link abaixo no APP e role a tela que verá a roleta caso seja selecionado(a)

É uma promoção de app (sem produto), mas caía em 'outros' por não citar
código, percentual ou a palavra 'cupom'.

O classificador já foi corrigido; esta migration reaplica em ofertas antigas.
"""
from django.db import migrations


def reclassificar_roleta_app(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _eh_anuncio_app_roleta

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        if not any(_eh_anuncio_app_roleta(linha) for linha in texto.split('\n')):
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
        print(f'Anuncios de roleta reclassificados de outros para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0178_reclassificar_bundle_console'),
    ]

    operations = [
        migrations.RunPython(reclassificar_roleta_app, migrations.RunPython.noop),
    ]
