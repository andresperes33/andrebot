from django.core.management.base import BaseCommand
from bot.models import Promo
from bot.classifier import detectar_categoria
from bot.services import _linha_titulo, _chave_produto


class Command(BaseCommand):
    help = "Reclassifica a categoria e recalcula a chave de produto de TODAS as promoções (corrige erros acumulados)."

    def handle(self, *args, **options):
        mudou_cat = 0
        mudou_chave = 0
        for promo in Promo.objects.all().iterator():
            texto = promo.texto_original or promo.titulo
            titulo = _linha_titulo(texto)
            nova = detectar_categoria(texto, titulo=titulo)
            chave = _chave_produto(promo.titulo) or _chave_produto(titulo)

            atualizar = []
            if nova and nova != promo.categoria:
                promo.categoria = nova
                mudou_cat += 1
                atualizar.append('categoria')
            if chave and chave != promo.produto_chave:
                promo.produto_chave = chave
                mudou_chave += 1
                atualizar.append('produto_chave')

            if atualizar:
                promo.save(update_fields=atualizar)

        self.stdout.write(self.style.SUCCESS(
            f"Processado. Categorias alteradas: {mudou_cat} | Chaves recalculadas: {mudou_chave}"
        ))
