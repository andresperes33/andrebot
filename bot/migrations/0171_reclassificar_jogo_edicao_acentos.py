"""Reclassifica jogos em 'outros' com edição em português (corrige acentos).

A migration 0170 comparava o texto sem remover acentos: o padrão `edicao`
não casava com `Edição`, então ofertas como
'LEGO Horizon Adventures Edição Standard' continuavam em 'outros'.

Esta migration refaz a mesma reclassificação, agora normalizando o texto
(sem acentos) antes de procurar a edição. Necessária para bancos onde a
0170 já foi aplicada com o bug.
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
        if not _RE_EDICAO_JOGO.search(_sem_acento(texto)):
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
        print(f'Jogos reclassificados de outros para jogo (acentos): {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0170_reclassificar_jogo_edicao'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_jogo, migrations.RunPython.noop
        ),
    ]
