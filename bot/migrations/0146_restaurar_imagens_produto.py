"""Restaura a imagem do produto nas promoções que ficaram com a imagem fixa de
cupom (cupom_ml_*) por causa da 0144, mas que NÃO são cupom. Baixa a imagem da
página do produto e atualiza. Se não conseguir baixar, mantém a imagem atual."""
import os
import tempfile

from django.db import migrations
from django.conf import settings


def restaurar_imagens(apps, schema_editor):
    from bot.services import baixar_imagem_produto, _converter_para_webp
    Promo = apps.get_model('bot', 'Promo')

    qs = Promo.objects.filter(
        imagem_url__contains='cupom_ml_',
    ).exclude(categoria='cupom')

    destino = os.path.join(settings.MEDIA_ROOT, 'promos')
    os.makedirs(destino, exist_ok=True)

    ok = 0
    sem = 0
    erros = 0
    for promo in qs.iterator():
        texto = promo.texto_original or promo.titulo or ''
        try:
            caminho = baixar_imagem_produto(texto, tempfile.gettempdir())
            if caminho and os.path.exists(caminho):
                fn, _path = _converter_para_webp(caminho, destino, prefixo='promo')
                if fn:
                    promo.imagem_url = f"{settings.MEDIA_URL.rstrip('/')}/promos/{fn}"
                    promo.save(update_fields=['imagem_url'])
                    ok += 1
                    continue
            sem += 1
        except Exception:
            erros += 1

    print(f'Imagens restauradas: {ok} | sem imagem: {sem} | erros: {erros}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0145_reverter_cupom_ml'),
    ]

    operations = [
        migrations.RunPython(restaurar_imagens, migrations.RunPython.noop),
    ]