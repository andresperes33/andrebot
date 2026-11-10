"""Reclassifica jogos vendidos como 'Nome - PS5' / 'Nome (PS5)' que a regra
antiga marcava como 'console' (ex.: 'Resident Evil Requiem - Ps5').

Só mexe em promoções que estão em 'console' e cujo título tem o formato de
jogo (nome + plataforma ao final). Consoles e acessórios ficam intactos.
"""
import re
import unicodedata
from django.db import migrations


def _norm(texto):
    base = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode('ascii')
    base = re.sub(r'[^\w\s.,!?/()\-|]', ' ', base)
    return re.sub(r'\s+', ' ', base).lower().strip()


_PLATAFORMA = (
    r'(?:ps\s*[1-5]|playstation\s*[1-5]|xbox(?:\s*series\s*[sx])?|'
    r'nintendo\s*switch|switch)'
)
_NAO_JOGO = (
    r'\b(?:console|videogame|sony|microsoft|kit|capa|case|suporte|'
    r'controle|controlador|gamepad|joystick|headset|fone|carregador|'
    r'cabo|ssd|hd|memoria)\b'
)


def _parece_jogo(titulo):
    """Cópia da regra de bot.classifier para o formato 'Nome - PS5'."""
    t = _norm(titulo)
    if not t:
        return False
    m = re.search(
        r'^(?P<nome>.+?)\s*(?:[-|]|\()?\s*' + _PLATAFORMA + r'\s*\)?\s*$',
        t,
    )
    if not m:
        return False
    nome = m.group('nome')
    if len(re.findall(r'[a-z0-9]+', nome)) < 2:
        return False
    if re.search(_NAO_JOGO, nome):
        return False
    return True


def reclassificar(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    atualizados = 0
    for promo in Promo.objects.filter(categoria='console').iterator():
        titulo = promo.titulo or ''
        primeira_linha = (promo.texto_original or '').split('\n')[0]
        if _parece_jogo(titulo) or _parece_jogo(primeira_linha):
            promo.categoria = 'jogo'
            promo.save(update_fields=['categoria'])
            atualizados += 1
    if atualizados:
        print(f'Jogos reclassificados de console -> jogo: {atualizados}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0149_promo_link_produto_chave'),
    ]

    operations = [
        migrations.RunPython(reclassificar, migrations.RunPython.noop),
    ]
