from django.db import migrations
from bot.services import _preco_do_texto, _linha_titulo
from bot.classifier import detectar_categoria


def corrigir(apps, schema_editor):
    """Corrige o preço de promos que pegaram o valor de frete/comissão
    ('- O da Shopee cobra R$ 400,00++ de frete') em vez do preço real."""
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        preco = _preco_do_texto(texto)
        atualizar = []
        if preco and preco != promo.preco:
            promo.preco = preco
            atualizar.append('preco')
        titulo = _linha_titulo(texto)
        if titulo and titulo != promo.titulo:
            promo.titulo = titulo
            atualizar.append('titulo')
        nova = detectar_categoria(texto, titulo=titulo)
        if nova and nova != promo.categoria:
            promo.categoria = nova
            atualizar.append('categoria')
        if atualizar:
            promo.save(update_fields=atualizar)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0117_reclassificar_teclados_tablet'),
    ]

    operations = [
        migrations.RunPython(corrigir, noop),
    ]
