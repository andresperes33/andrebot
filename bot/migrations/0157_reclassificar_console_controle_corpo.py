"""Reclassifica ofertas salvas de console/controle após corrigir o bundle.

A migration 0156 reaproveitou o classificador, mas o classificador ainda
deixava o CORPO do texto roubar a categoria: quando o texto salvo começa em
'PARCELADO!' (sem a linha do título), a palavra 'controle' no corpo vencia
antes da regra de bundle de console. Resultado: o console PS5 com controle
incluso continuava como 'controle'.

Esta migration roda o classificador já corrigido sobre as ofertas salvas.
"""
from django.db import migrations


def reclassificar_console_controle(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo

    Promo = apps.get_model('bot', 'Promo')
    n = 0
    for promo in Promo.objects.filter(
        categoria__in=['controle', 'console']
    ).iterator():
        texto = promo.texto_original or promo.titulo or ''
        if not texto:
            continue
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if correta == promo.categoria:
            continue
        promo.categoria = correta
        update_fields = ['categoria']
        if titulo and promo.titulo != titulo:
            promo.titulo = titulo[:250]
            update_fields.append('titulo')
        promo.save(update_fields=update_fields)
        n += 1

    if n:
        print(f'Ofertas de console/controle reclassificadas: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0156_reclassificar_console_acessorio'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_console_controle, migrations.RunPython.noop
        ),
    ]
