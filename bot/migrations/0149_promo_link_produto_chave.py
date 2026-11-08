"""Adiciona a chave canônica do link do produto (deduplicação diária).

A chave é usada pelo monitor para não postar a mesma oferta duas vezes no
mesmo dia, mesmo que canais diferentes usem formatos/links diferentes para
o mesmo produto.
"""
from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def backfill_link_produto_chave(apps, schema_editor):
    from bot.services import _chave_link_produto, _primeiro_link_produto

    Promo = apps.get_model('bot', 'Promo')
    limite = timezone.now() - timedelta(days=7)
    for promo in Promo.objects.filter(
        link_produto_chave='', criado_em__gte=limite
    ).iterator():
        if promo.categoria == 'cupom':
            continue
        link = promo.link_afiliado or _primeiro_link_produto(promo.texto_original or '')
        chave = _chave_link_produto(link)
        if chave:
            promo.link_produto_chave = chave
            promo.save(update_fields=['link_produto_chave'])


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0148_reclassificar_cupons_outros'),
    ]

    operations = [
        migrations.AddField(
            model_name='promo',
            name='link_produto_chave',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                help_text=(
                    'Chave canônica do link do produto (sem preço/rastreio) — '
                    'usada para não repetir a mesma oferta no mesmo dia entre canais.'
                ),
                max_length=1000,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(
            backfill_link_produto_chave, migrations.RunPython.noop
        ),
    ]
