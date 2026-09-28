import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand

from bot.models import Promo


class Command(BaseCommand):
    help = ("Restaura a imagem ORIGINAL do produto direto do disco (media/promos), "
            "sem depender do ML/loja (que bloqueiam o servidor). As promos que a "
            "migração 0144 deixou com imagem cupom_ml_* voltam para o arquivo "
            "original, localizado pelo timestamp do nome do arquivo x criado_em.")

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=0,
                            help="Máx. de promoções a processar (0 = todas).")

    def handle(self, *args, **opts):
        limite = opts.get("limite") or 0
        media_promos = os.path.join(settings.MEDIA_ROOT, "promos")
        if not os.path.isdir(media_promos):
            self.stdout.write(self.style.ERROR(f"Pasta não encontrada: {media_promos}"))
            return

        # Índice: timestamp unix (extraído do nome) -> [arquivos]
        # Formatos: promo_<ts>_<base>.webp  |  produto_<ts><resto>.webp
        index = {}
        for nome in os.listdir(media_promos):
            m = re.match(r'(?:promo|produto)_(\d+)', nome)
            if not m:
                continue
            ts = int(m.group(1))
            index.setdefault(ts, []).append(nome)

        self.stdout.write(f"Arquivos originais indexados: {sum(len(v) for v in index.values())}")

        qs = Promo.objects.filter(
            imagem_url__contains="cupom_ml_",
        ).exclude(categoria="cupom")

        ok = 0
        sem = 0
        para_ver = 0
        processadas = 0
        for promo in qs.iterator():
            if limite and processadas >= limite:
                break
            processadas += 1
            try:
                alvo = int(promo.criado_em.timestamp())
            except Exception:
                sem += 1
                continue

            # candidatos num intervalo de ±5s (criação da imagem ≈ criação da promo)
            candidatos = []
            for ts in range(alvo - 5, alvo + 6):
                for nome in index.get(ts, []):
                    candidatos.append(nome)

            if not candidatos:
                sem += 1
                self.stdout.write(self.style.WARNING(f"sem arquivo {promo.pk} (ts={alvo})"))
                continue

            # se mais de um, escolhe o mais próximo do timestamp exato
            melhor = min(candidatos, key=lambda n: abs(_ts_de(n) - alvo))
            if len(candidatos) > 1:
                para_ver += 1
                self.stdout.write(f"ambiguo {promo.pk}: {candidatos[:4]}")

            promo.imagem_url = f"{settings.MEDIA_URL.rstrip('/')}/promos/{melhor}"
            promo.save(update_fields=["imagem_url"])
            ok += 1

        self.stdout.write(self.style.SUCCESS(
            f"Pronto: {ok} restauradas, {sem} sem arquivo, {para_ver} ambiguas, {processadas} processadas."
        ))


def _ts_de(nome):
    m = re.match(r'(?:promo|produto)_(\d+)', nome)
    return int(m.group(1)) if m else 0