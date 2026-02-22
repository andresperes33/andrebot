from django.core.management.base import BaseCommand
from bot.telegram_bot import start_bot

class Command(BaseCommand):
    help = 'Inicia o bot do Telegram para conversão de links de afiliado'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando o bot...'))
        try:
            start_bot()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Bot interrompido.'))
