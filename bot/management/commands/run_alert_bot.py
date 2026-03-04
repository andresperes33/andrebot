from django.core.management.base import BaseCommand
from bot.alert_bot import run_alert_bot


class Command(BaseCommand):
    help = 'Inicia o Bot de Alertas de Promoções (@andreindica_bot)'

    def handle(self, *args, **options):
        self.stdout.write('🤖 Iniciando Bot de Alertas...')
        run_alert_bot()
