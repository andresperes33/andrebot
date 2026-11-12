"""Reclassifica ofertas de memória RAM salvas como 'jogo'.

Caso alvo: 'Memória RAM JUHOR DDR4 8GB 3200MHz CL16 Ruivinha Anime'.
O corpo da oferta cita "jogo de impulso" (marketing do canal), o que fazia
a regra de jogo vencer a de memória RAM. O classificador já foi corrigido;
esta migration reaplica a classificação nas ofertas antigas.
"""
import re

from django.db import migrations


_TERMOS_RAM = re.compile(
    r'\b(?:mem[oó]ria\s*ram|ram\s+ddr[345]|ddr[345]\s+\d+\s*gb|'
    r'pente\s+de\s+mem[oó]ria|sodimm)\b',
    re.IGNORECASE,
)


def reclassificar_ram_jogo(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0
    for promo in Promo.objects.filter(categoria='jogo').iterator():
        texto = promo.texto_original or promo.titulo or ''
        if not _TERMOS_RAM.search(texto):
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta != 'memoria_ram':
            continue
        promo.categoria = 'memoria_ram'
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'Memorias RAM reclassificadas de jogo para memoria_ram: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0158_reclassificar_cupom_codigo'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_ram_jogo, migrations.RunPython.noop
        ),
    ]
