import re
from django.core.management.base import BaseCommand
from bot.models import Promo
from bot.services import _link_produto_compra


class Command(BaseCommand):
    help = 'Corrige link_afiliado de promoções que apontam para serviços (Amazon Prime, Netflix, etc.)'

    def handle(self, *args, **options):
        service_patterns = [
            'amazonprime', '/prime?', '/prime',
            'netflix', 'disney+', 'hbo+', 'spotify',
            'apple.music', 'steam', 'pago.com.br',
        ]
        corrigidas = 0
        for promo in Promo.objects.all():
            link = promo.link_afiliado or ''
            if not any(p in link for p in service_patterns):
                continue
            novo = _link_produto_compra(promo.texto_original or '')
            if novo and novo != link:
                promo.link_afiliado = novo
                promo.save(update_fields=['link_afiliado'])
                self.stdout.write(f'Promo {promo.pk}: {link[:60]} -> {novo[:60]}')
                corrigidas += 1
        self.stdout.write(self.style.SUCCESS(f'Total corrigidas: {corrigidas}'))
