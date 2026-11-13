"""Reclassifica listas de cupons que caíram em 'celular'/'outros'.

Caso alvo: lista de cupons da Shopee que começa com 'Cupom válido para todos
os itens' e tem a seção 'Auto & Moto'. O termo 'moto' (de 'Auto & Moto') era
lido como a marca Motorola, e a oferta virava 'celular' — ou, sem o rótulo,
'outros'. Agora 'Auto & Moto' é reconhecido como rótulo de seção e a
postagem é 'cupom'. O classificador já foi corrigido; esta migration
reaplica a classificação nas ofertas antigas.
"""
import re
from django.db import migrations


def reclassificar_lista_cupons(apps, schema_editor):
    from bot.classifier import detectar_categoria, _norm
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0
    for promo in Promo.objects.filter(categoria__in=('celular', 'outros')).iterator():
        texto = promo.texto_original or promo.titulo or ''
        primeira = next(
            (linha for linha in texto.splitlines() if linha.strip()), ''
        )
        if not re.match(
            r'^(?:nov[oa]s?|pr[oó]x[ií]m[oa]s?|ultim[oa]s?)?\s*cupons?\b',
            _norm(primeira),
        ):
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
        print(f'Listas de cupons reclassificadas para cupom: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0162_reclassificar_cooler_jogo'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_lista_cupons, migrations.RunPython.noop
        ),
    ]
