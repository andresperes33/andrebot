import os
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand

from bot.models import Promo
from bot.services import baixar_imagem_produto, _converter_para_webp


class Command(BaseCommand):
    help = ("Restaura a imagem do produto nas promoções que ficaram com a imagem "
            "fixa de cupom (cupom_ml_*) por causa da migração 0144, mas que NÃO "
            "são cupom. Baixa a imagem da página do produto e atualiza.")

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
        erros = 0
        for promo in qs.iterator():
            if limite and processadas >= limite:
                break
            processadas += 1
            texto = promo.texto_original or promo.titulo or ""
            try:
                caminho = baixar_imagem_produto(texto, tempfile.gettempdir())
                if caminho and os.path.exists(caminho):
                    fn, _path = _converter_para_webp(caminho, destino, prefixo="promo")
                    if fn:
                        promo.imagem_url = f"{settings.MEDIA_URL.rstrip('/')}/promos/{fn}"
                        promo.save(update_fields=["imagem_url"])
                        ok += 1
                        self.stdout.write(f"OK promo {promo.pk} -> {fn}")
                        continue
                self.stdout.write(f"sem imagem {promo.pk}")
            except Exception as err:
                erros += 1
                self.stdout.write(self.style.ERROR(f"ERRO promo {promo.pk}: {err}"))

        self.stdout.write(self.style.SUCCESS(
            f"Pronto: {ok} imagens restauradas, {erros} erros, {processadas} processadas."
        ))