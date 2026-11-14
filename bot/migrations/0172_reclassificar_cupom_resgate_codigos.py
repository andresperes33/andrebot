"""Reclassifica anúncios de cupom COM CÓDIGOS salvos como 'outros'.

Caso alvo: '‼️ Aliexpress renovou alguns cupons, confira no APP' +
'Tente resgatar os AEMEGA1 ... e VAMOS01 ...'. A linha de instrução de
resgate era confundida com nome de produto (os códigos pareciam modelo),
então a oferta caía em 'outros'.

O classificador já foi corrigido; esta migration reaplica a classificação
nas ofertas antigas de 'outros' que citam cupom + códigos.
"""
import re

from django.db import migrations


def reclassificar_cupons_codigos(apps, schema_editor):
    from bot.classifier import _eh_anuncio_cupom_codigos, detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        # 'cupom' NÃO é substring de 'cupons' (m → n no plural).
        if not re.search(r'\bcupons?\b', texto, re.IGNORECASE):
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        if not _eh_anuncio_cupom_codigos(texto, titulo):
            continue
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
        print(f'Cupons com codigos reclassificados de outros para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0171_reclassificar_jogo_edicao_acentos'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_cupons_codigos, migrations.RunPython.noop
        ),
    ]
