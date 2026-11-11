"""Reclassifica ofertas salvas como 'controle'/'console' que estão na categoria errada.

Casos alvo:
- Console PS5 com controle incluso (ex.: 'PS5 PlayStation 5 Edição Digital
  825GB 1 Controle Branco Sony com 2 Jogos ...') estava como 'controle' por
  causa do rótulo 'Controle / Gamepad' antes do título; deve ser 'console'.
- Acessórios de corrida (ex.: 'Câmbio Logitech G Driving Force ... para PS5,
  PS4, Xbox ...') estavam como 'console' por citar as plataformas na lista de
  compatibilidade; devem ser 'acessorio'.

Reaproveita o classificador atual (fonte de verdade) e atualiza também o
título quando a linha correta do produto é outra.
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
        ('bot', '0155_reclassificar_cupom_desconto'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_console_controle, migrations.RunPython.noop
        ),
    ]
