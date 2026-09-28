import os
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand

from bot.models import Promo
from bot.services import get_product_info, _converter_para_webp, _primeiro_link_produto


class Command(BaseCommand):
    help = ("Restaura a imagem do produto nas promoções que ficaram com a imagem "
            "fixa de cupom (cupom_ml_*) por causa da migração 0144, mas que NÃO "
            "são cupom. Usa get_product_info (mais robusto) para achar a imagem "
            "e baixa. Imprime o motivo de cada falha.")

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=0,
                            help="Máx. de promoções a processar (0 = todas).")

    def handle(self, *args, **opts):
        limite = opts.get("limite") or 0
        qs = Promo.objects.filter(
            imagem_url__contains="cupom_ml_",
        ).exclude(categoria="cupom")
        total = qs.count()
        self.stdout.write(f"Promos com imagem de cupom (não-cupom): {total}")

        destino = os.path.join(settings.MEDIA_ROOT, "promos")
        os.makedirs(destino, exist_ok=True)

        processadas = 0
        ok = 0
        sem = 0
        erros = 0
        for promo in qs.iterator():
            if limite and processadas >= limite:
                break
            processadas += 1
            texto = promo.texto_original or promo.titulo or ""
            link = _primeiro_link_produto(texto)
            if not link:
                sem += 1
                self.stdout.write(self.style.WARNING(f"sem link {promo.pk}"))
                continue
            try:
                _nome, img_url, _preco = get_product_info(link)
            except Exception as err:
                erros += 1
                self.stdout.write(self.style.ERROR(f"erro {promo.pk} {link[:60]}: {err}"))
                continue
            if not img_url:
                sem += 1
                self.stdout.write(self.style.WARNING(f"sem imagem {promo.pk} {link[:60]}"))
                continue
            try:
                import io
                import requests as _requests
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                ri = _requests.get(img_url, headers=headers, timeout=20)
                if ri.status_code != 200 or not ri.content:
                    sem += 1
                    self.stdout.write(self.style.WARNING(f"download falhou {promo.pk} {img_url[:60]}"))
                    continue
                tmp = os.path.join(tempfile.gettempdir(), f"rest_{promo.pk}.img")
                with open(tmp, "wb") as f:
                    f.write(ri.content)
                fn, _path = _converter_para_webp(tmp, destino, prefixo="promo")
                if not fn:
                    sem += 1
                    self.stdout.write(self.style.WARNING(f"conversao falhou {promo.pk}"))
                    continue
                promo.imagem_url = f"{settings.MEDIA_URL.rstrip('/')}/promos/{fn}"
                promo.save(update_fields=["imagem_url"])
                ok += 1
                self.stdout.write(f"OK {promo.pk} -> {fn}")
            except Exception as err:
                erros += 1
                self.stdout.write(self.style.ERROR(f"erro baixar {promo.pk}: {err}"))

        self.stdout.write(self.style.SUCCESS(
            f"Pronto: {ok} ok, {sem} sem imagem, {erros} erros, {processadas} processadas."
        ))