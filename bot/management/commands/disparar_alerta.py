"""
Dispara os alertas (Telegram + Nitro Alerta/WhatsApp) para uma promoção
específica, manualmente. Útil quando o monitor automático não disparou.

Uso:
    python manage.py disparar_alerta --promo 1234
    python manage.py disparar_alerta --texto "Placa de Vídeo ... Link: https://..."
"""
from django.core.management.base import BaseCommand, CommandError
from bot.models import Promo


class Command(BaseCommand):
    help = 'Dispara manualmente os alertas (Telegram e Nitro Alerta/WhatsApp) para uma promoção.'

    def add_arguments(self, parser):
        parser.add_argument('--promo', type=int, default=None,
                            help='ID da promoção salva no banco.')
        parser.add_argument('--texto', type=str, default=None,
                            help='Texto da oferta (quando não quiser usar uma promo salva).')

    def handle(self, *args, **options):
        from bot.alert_sender import send_alerts
        from bot.alert_site import send_alerts_site
        from bot.classifier import detectar_categoria
        from bot.services import _linha_titulo

        promo_id = options.get('promo')
        texto = options.get('texto')

        if promo_id:
            promo = Promo.objects.filter(pk=promo_id).first()
            if not promo:
                raise CommandError(f'Promo {promo_id} não encontrada.')
            texto = promo.texto_original or promo.titulo
            categoria = promo.categoria
            foto = promo.imagem_url or None
            self.stdout.write(f'Promo {promo_id} — categoria: {categoria}')
            self.stdout.write(f'Título: {promo.titulo[:80]}')
        elif texto:
            categoria = detectar_categoria(texto, titulo=_linha_titulo(texto))
            foto = None
            self.stdout.write(f'Categoria detectada: {categoria}')
        else:
            raise CommandError('Informe --promo <id> ou --texto "<oferta>".')

        self.stdout.write('Enviando alertas Telegram...')
        send_alerts(texto, photo_path=foto, oferta_categoria=categoria)

        self.stdout.write('Enviando Nitro Alerta (WhatsApp)...')
        send_alerts_site(texto, photo_path=foto, oferta_categoria=categoria)

        self.stdout.write(self.style.SUCCESS('Disparo concluído.'))