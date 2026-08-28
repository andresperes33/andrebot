from django.core.management.base import BaseCommand
from bot.models import Promo
from bot.classifier import detectar_categoria
from bot.services import _linha_titulo, _chave_produto, _preco_do_texto


class Command(BaseCommand):
    help = "Reclassifica categoria, recalcula título/preço/chave de TODAS as promoções (corrige erros acumulados)."

    def handle(self, *args, **options):
        mudou_cat = 0
        mudou_chave = 0
        mudou_titulo = 0
        mudou_preco = 0
        for promo in Promo.objects.all().iterator():
            texto = promo.texto_original or promo.titulo
            # Título corrigido a partir do texto original (ignora instruções)
            titulo = _linha_titulo(texto) or promo.titulo
            nova = detectar_categoria(texto, titulo=titulo)
            preco = _preco_do_texto(texto)
            # Chave recalculada usando o título CORRIGIDO (não o antigo salvo)
            chave = _chave_produto(titulo) or _chave_produto(promo.titulo)

            atualizar = []
            if nova and nova != promo.categoria:
                promo.categoria = nova
                mudou_cat += 1
                atualizar.append('categoria')
            if titulo and titulo != promo.titulo:
                promo.titulo = titulo
                mudou_titulo += 1
                atualizar.append('titulo')
            if preco and preco != promo.preco:
                promo.preco = preco
                mudou_preco += 1
                atualizar.append('preco')
            if chave and chave != promo.produto_chave:
                promo.produto_chave = chave
                mudou_chave += 1
                atualizar.append('produto_chave')

            if atualizar:
                promo.save(update_fields=atualizar)

        self.stdout.write(self.style.SUCCESS(
            f"Processado. Categorias alteradas: {mudou_cat} | Títulos corrigidos: {mudou_titulo} | "
            f"Preços corrigidos: {mudou_preco} | Chaves recalculadas: {mudou_chave}"
        ))
