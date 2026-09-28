"""Reclassifica promoções de CUPOM do Mercado Livre que foram salvas como
'outros' (ou outra categoria) e troca a imagem pela imagem fixa do cupom ML."""
import os
import time

from django.db import migrations
from django.conf import settings


def _caminho_imagem_cupom_ml():
    for base in (
        os.path.join(settings.MEDIA_ROOT, 'cupom'),
        os.path.join(settings.BASE_DIR, 'bot', 'static', 'bot', 'cupom'),
        os.path.join(settings.BASE_DIR, 'staticfiles', 'bot', 'cupom'),
    ):
        p = os.path.join(base, 'cupom_mercado_livre.jpg')
        if os.path.exists(p):
            return p
    return None


def reclassificar_cupom_ml(apps, schema_editor):
    from PIL import Image
    Promo = apps.get_model('bot', 'Promo')

    origem = _caminho_imagem_cupom_ml()
    if not origem:
        print('⚠️ Imagem de cupom ML não encontrada — apenas reclassificando categoria/loja.')
    media_promos = os.path.join(settings.MEDIA_ROOT, 'promos')
    if origem:
        os.makedirs(media_promos, exist_ok=True)

    n = 0
    for promo in Promo.objects.exclude(categoria='cupom').iterator():
        texto = (promo.texto_original or promo.titulo or '').casefold()
        eh_cupom = 'cupom' in texto or 'cupons' in texto
        eh_ml = any(m in texto for m in ('mercado livre', 'mercadolivre', 'meli.la', 'meli '))
        if not (eh_cupom and eh_ml):
            continue

        promo.categoria = 'cupom'
        promo.loja = 'Mercado Livre'

        if origem:
            try:
                with Image.open(origem) as img:
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGBA')
                        fundo = Image.new('RGB', img.size, (255, 255, 255))
                        fundo.paste(img, mask=img.split()[-1])
                        img = fundo
                    else:
                        img = img.convert('RGB')
                    filename = f'cupom_ml_{int(time.time())}_{promo.pk}.webp'
                    img.save(os.path.join(media_promos, filename), 'WEBP', quality=82)
                promo.imagem_url = f"{settings.MEDIA_URL.rstrip('/')}/promos/{filename}"
            except Exception as err:
                print(f'⚠️ Erro ao salvar imagem do cupom ML (promo {promo.pk}): {err}')

        promo.save(update_fields=['categoria', 'loja', 'imagem_url'])
        n += 1

    if n:
        print(f'Cupons ML reclassificados para cupom (imagem trocada): {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0143_reclassificar_relogio_inteligente'),
    ]

    operations = [
        migrations.RunPython(reclassificar_cupom_ml, migrations.RunPython.noop),
    ]