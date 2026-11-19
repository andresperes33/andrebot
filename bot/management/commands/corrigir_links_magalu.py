"""Reconverte links da Magalu salvos como vitrine (sem o PID do produto).

O formato '/magalu/divulgador/oferta/<PID>/...' dos links aoferta.net não
era reconhecido pelo conversor, que gerava
'magazinevoce.com.br/<loja>/magalu/p/produto/' (vitrine genérica).

Uso:
    python manage.py corrigir_links_magalu
"""
import re

from django.core.management.base import BaseCommand

from bot.models import Promo
from bot.services import convert_to_affiliate_link

_RE_LINK = re.compile(
    r'https?://(?:[a-z0-9.-]*aoferta\.net/|'
    r'(?:www\.)?magazineluiza\.com\.br/|'
    r'(?:www\.)?magalu\.com(?:\.br)?/|'
    r'mgl\.io/|'
    r'(?:www\.)?magazinevoce\.com\.br/)\S+',
    re.IGNORECASE,
)
_RE_PID = re.compile(r'/p/\d{6,}/')
_SUFIXO = '.,;:!?\'")]}'


class Command(BaseCommand):
    help = 'Reconverte links da Magalu salvos como vitrine'

    def handle(self, *args, **options):
        corrigidas = 0
        falhas = 0

        for promo in Promo.objects.all().iterator():
            texto = promo.texto_original or ''
            links = [u.rstrip(_SUFIXO) for u in _RE_LINK.findall(texto)]
            link_salvo = (promo.link_afiliado or '').rstrip(_SUFIXO)

            # Já é link de produto com PID válido: nada a fazer.
            if _RE_PID.search(link_salvo):
                continue

            if link_salvo and _RE_LINK.search(link_salvo):
                links.append(link_salvo)
            links = [u for u in links if u]
            if not links:
                continue

            # aoferta.net é a URL original e costuma resolver o PID correto.
            links.sort(key=lambda u: 0 if 'aoferta.net' in u else 1)

            convertido = None
            for link in links:
                try:
                    candidato = convert_to_affiliate_link(link)
                except Exception:
                    candidato = None
                if candidato and _RE_PID.search(candidato):
                    convertido = candidato
                    break

            if not convertido:
                falhas += 1
                self.stdout.write(f'Promo {promo.pk}: sem PID identificavel')
                continue

            if convertido == promo.link_afiliado:
                continue

            for link in set(links):
                texto = texto.replace(link, convertido)
            promo.link_afiliado = convertido
            promo.texto_original = texto
            promo.save(update_fields=['link_afiliado', 'texto_original'])
            corrigidas += 1
            self.stdout.write(f'Promo {promo.pk}: -> {convertido[:110]}')

        self.stdout.write(self.style.SUCCESS(
            f'Corrigidas: {corrigidas} | sem conversao: {falhas}'
        ))
