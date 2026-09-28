"""Reverte a 0144: reclassifica de volta as promoções que foram marcadas como
cupom ML indevidamente (ex.: produto com cupom + Mercado Livre). Usa o
classificador atual para decidir a categoria correta e restaura loja/imagem."""
import os

from django.db import migrations
from django.conf import settings


def reverter_cupom_ml(apps, schema_editor):
    from bot.classifier import detectar_categoria, detectar_loja
    from bot.services import _linha_titulo, baixar_imagem_produto, _converter_para_webp
    Promo = apps.get_model('bot', 'Promo')

    # Promos que a 0144 tocou: cupom + loja ML + imagem 'cupom_ml_'
    qs = Promo.objects.filter(
        categoria='cupom',
        loja='Mercado Livre',
        imagem_url__contains='cupom_ml_',
    )
    n = 0
    for promo in qs.iterator():
        texto = promo.texto_original or promo.titulo or ''
        titulo = _linha_titulo(texto) or promo.titulo
        try:
            correta = detectar_categoria(texto, titulo=titulo)
        except Exception:
            continue
        if not correta or correta == 'cupom':
            continue  # é cupom mesmo — mantém

        promo.categoria = correta
        promo.loja = detectar_loja(promo.link_afiliado)

        # Tenta restaurar a imagem do produto (se conseguir)
        try:
            import tempfile
            caminho = baixar_imagem_produto(texto, tempfile.gettempdir())
            if caminho and os.path.exists(caminho):
                destino = os.path.join(settings.MEDIA_ROOT, 'promos')
                os.makedirs(destino, exist_ok=True)
                fn, _path = _converter_para_webp(caminho, destino, prefixo='promo')
                if fn:
                    promo.imagem_url = f"{settings.MEDIA_URL.rstrip('/')}/promos/{fn}"
        except Exception as err:
            print(f'⚠️ Não restaurou imagem da promo {promo.pk}: {err}')

        promo.save(update_fields=['categoria', 'loja', 'imagem_url'])
        n += 1

    if n:
        print(f'Promoções revertidas (não eram cupom): {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0144_reclassificar_cupom_ml'),
    ]

    operations = [
        migrations.RunPython(reverter_cupom_ml, migrations.RunPython.noop),
    ]