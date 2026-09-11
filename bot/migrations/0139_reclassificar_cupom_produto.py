from django.db import migrations
from bot.classifier import detectar_categoria
from bot.services import _linha_titulo


def reclassificar(apps, schema_editor):
    """Reclassifica promoções que foram marcadas como 'cupom' quando na verdade
    o texto traz um produto real (ex.: 'Cupom ... RTX 5070 TI Placa de Video
    ... R$100 OFF'). A correção em detectar_categoria agora ignora a linha
    'Cupom' e as linhas de estoque ('ÚLTIMAS 7 UNIDADES') ao detectar produto."""
    Promo = apps.get_model('bot', 'Promo')
    alteradas = 0
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        if not texto:
            continue
        titulo = _linha_titulo(texto)
        nova = detectar_categoria(texto, titulo=titulo)
        if nova and nova != promo.categoria:
            promo.categoria = nova
            promo.save(update_fields=['categoria'])
            alteradas += 1
    if alteradas:
        print(f'Reclassificadas {alteradas} promocoes.')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0138_corrigir_categorias'),
    ]

    operations = [
        migrations.RunPython(reclassificar, noop),
    ]