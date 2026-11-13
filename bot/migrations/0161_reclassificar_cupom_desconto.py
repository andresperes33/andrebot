"""Reclassifica anúncios de cupom/desconto salvos como 'outros'.

Caso alvo: '10% EM PLACAS DE VÍDEO ZAFADINHO10' (KaBuM). A primeira linha
começa pelo percentual de desconto e traz o código do cupom; o termo 'placas
de vídeo' fazia a oferta cair em 'outros', então ela entrava nas ofertas em
vez de ser bloqueada como cupom. O classificador já foi corrigido; esta
migration reaplica a classificação nas ofertas antigas.
"""
import re
from django.db import migrations


def reclassificar_cupom_desconto(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0
    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        # Só interessa quando o começo do texto é uma linha de desconto
        # ('10% EM ...', '50% OFF ...').
        linhas = [l for l in texto.splitlines() if l.strip()]
        if not any(re.match(r'^\s*\d{1,3}\s*%', l) for l in linhas[:5]):
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
        print(f'Anúncios de cupom/desconto reclassificados de outros para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0160_reclassificar_alerta_cupom'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_cupom_desconto, migrations.RunPython.noop
        ),
    ]
