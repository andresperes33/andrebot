"""Reclassifica jogos em 'outros' por terem edição em português no título.

Caso alvo: 'LEGO Horizon Adventures Edição Standard'. A regra de coleções de
jogo só reconhecia 'edition' em inglês; 'edição' (padrão, deluxe, ultimate,
completa etc.) não era detectada e a oferta caía em 'outros'.

O classificador já foi corrigido; esta migration reaplica a classificação nas
ofertas antigas de 'outros'.
"""
import re
import unicodedata
from django.db import migrations


_RE_EDICAO_JOGO = re.compile(
    r'\bedicao\s+(?:standard|padrao|deluxe|ultimate|completa|completo|'
    r'gold|premium|especial|limitada|definitiva)\b'
    r'|\bgame\s+of\s+the\s+year\b|\bgoty\b'
)


def _sem_acento(texto):
    return unicodedata.normalize('NFKD', texto or '').encode(
        'ascii', 'ignore'
    ).decode('ascii').casefold()


def reclassificar_jogo(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='outros').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = _sem_acento(texto)
        if not _RE_EDICAO_JOGO.search(baixa):
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'jogo':
            continue
        promo.categoria = 'jogo'
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'Jogos reclassificados de outros para jogo: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0169_reclassificar_tv_caixa_som'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_jogo, migrations.RunPython.noop
        ),
    ]
