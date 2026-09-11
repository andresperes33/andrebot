import os

from django.core.management.base import BaseCommand
from django.conf import settings

from bot.models import Promo
from bot.services import _converter_para_webp


class Command(BaseCommand):
    help = "Converte as imagens locais das promoções existentes para WebP (mais leves, rolagem mais fluida)."

    def handle(self, *args, **options):
        media_promos = os.path.join(settings.MEDIA_ROOT, 'promos')
        os.makedirs(media_promos, exist_ok=True)
        convertidas = puladas = erros = 0
        for promo in Promo.objects.all().iterator():
            url = promo.imagem_url or ''
            if not url.startswith(settings.MEDIA_URL):
                continue  # URL externa (hotlink) — não há arquivo local
            caminho = os.path.join(settings.MEDIA_ROOT, url[len(settings.MEDIA_URL):])
            if not os.path.exists(caminho):
                puladas += 1
                continue
            if caminho.lower().endswith('.webp'):
                puladas += 1
                continue
            filename, novo = _converter_para_webp(caminho, media_promos, prefixo=f'promo')
            if not filename or not novo:
                erros += 1
                print(f'⚠️ Falha ao converter promov #{promo.id}: {caminho}')
                continue
            promo.imagem_url = f"{settings.MEDIA_URL}promos/{filename}"
            promo.save(update_fields=['imagem_url'])
            convertidas += 1
            if convertidas <= 5 or convertidas % 25 == 0:
                print(f'✅ #{promo.id} -> {filename}')

        print(f'\nResumo: {convertidas} convertidas, {puladas} puladas, {erros} erros.')