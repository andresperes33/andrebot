"""Reconverte links meli.la / /social/ que ficaram salvos sem virar produto.

O Mercado Livre responde 500 intermitentemente nas páginas /social/. Antes da
correção no conversor, isso fazia o sistema salvar a própria URL /social/
(com os parâmetros matt) como se fosse o link de afiliado do produto.

Uso:
    python manage.py corrigir_links_meli
"""
import re

from django.core.management.base import BaseCommand

from bot.models import Promo
from bot.services import convert_mercado_livre_link

_RE_MELI = re.compile(
    r'https?://(?:[a-z0-9.-]*meli\.la/\S+|www\.mercadolivre\.com\.br/social/\S+)',
    re.IGNORECASE,
)


class Command(BaseCommand):
    help = 'Reconverte links do Mercado Livre salvos como pagina social'

    def handle(self, *args, **options):
        corrigidas = 0
        falhas = 0

        for promo in Promo.objects.all().iterator():
            links = _RE_MELI.findall(promo.texto_original or '')
            link_salvo = (promo.link_afiliado or '').rstrip('.,;:!?\'"')
            if link_salvo and _RE_MELI.fullmatch(link_salvo):
                links.append(link_salvo)
            if not links:
                continue

            # meli.la é a URL original; /social/ é o destino interno do ML.
            links.sort(key=lambda u: 0 if 'meli.la' in u else 1)

            convertido = None
            for link in links:
                try:
                    convertido = convert_mercado_livre_link(link.rstrip('.,;:!?\'"'))
                except Exception:
                    convertido = None
                if convertido:
                    break

            if not convertido:
                falhas += 1
                self.stdout.write(f'Promo {promo.pk}: nao foi possivel converter')
                continue

            if convertido == promo.link_afiliado:
                continue

            texto = promo.texto_original or ''
            for link in links:
                texto = texto.replace(link.rstrip('.,;:!?\'"'), convertido)
            promo.link_afiliado = convertido
            promo.texto_original = texto
            promo.save(update_fields=['link_afiliado', 'texto_original'])
            corrigidas += 1
            self.stdout.write(f'Promo {promo.pk}: -> {convertido[:100]}')

        self.stdout.write(self.style.SUCCESS(
            f'Corrigidas: {corrigidas} | sem conversao: {falhas}'
        ))
