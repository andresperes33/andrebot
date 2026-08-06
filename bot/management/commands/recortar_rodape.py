import os

from django.conf import settings
from django.core.management.base import BaseCommand

from bot.models import Promo
from bot.services import cortar_rodape_imagem


class Command(BaseCommand):
    help = "Recorta o rodapé das imagens de todas as promoções salvas localmente."

    def add_arguments(self, parser):
        parser.add_argument("--px", type=int, default=100,
                            help="Quantos pixels remover da base (default: 100).")

    def handle(self, *args, **opts):
        px = opts["px"]
        media_root = settings.MEDIA_ROOT
        cortadas = 0
        erros = 0
        feitas = set()

        for promo in Promo.objects.exclude(imagem_url="").exclude(imagem_url=None):
            url = promo.imagem_url
            if url.startswith("http") or url.startswith("//"):
                continue
            rel = url.strip()
            if rel.startswith(f"{settings.MEDIA_URL}"):
                rel = rel[len(settings.MEDIA_URL):]
            caminho = os.path.join(media_root, rel)
            caminho = os.path.normpath(caminho)
            if caminho in feitas:
                continue
            feitas.add(caminho)
            if not os.path.exists(caminho):
                continue
            try:
                cortar_rodape_imagem(caminho, px)
                entradas = Promo.objects.filter(imagem_url=url).count()
                cortadas += entradas
                self.stdout.write(f"OK {rel} ({entradas} promos)")
            except Exception as err:
                erros += 1
                self.stdout.write(self.style.ERROR(f"ERRO {cam}: {err}"))
        self.stdout.write(self.style.SUCCESS(
            f"Pronto: {len(feitas)} arquivos, {cortadas} promos atualizadas, {erros} erros."
        ))