"""
Envia manualmente o André Alerta (WhatsApp) de uma promoção para um número
específico. Útil para reenviar uma oferta que não chegou ao usuário.

Uso:
    python manage.py enviar_alerta_site --promo 20449 --whatsapp 5538999400711
    python manage.py enviar_alerta_site --promo 20449 --whatsapp 5538999400711 --dry-run
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from bot.models import AlertaSite, Promo


class Command(BaseCommand):
    help = 'Envia o André Alerta (WhatsApp) de uma promoção para um número específico.'

    def add_arguments(self, parser):
        parser.add_argument('--promo', type=int, required=True,
                            help='ID da promoção salva no banco.')
        parser.add_argument('--whatsapp', type=str, required=True,
                            help='Número de destino (ex.: 5538999400711).')
        parser.add_argument('--keyword', type=str, default=None,
                            help='Força a palavra-chave mostrada na mensagem.')
        parser.add_argument('--nome', type=str, default=None,
                            help='Força o nome mostrado na mensagem.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostra a mensagem sem enviar.')

    def handle(self, *args, **options):
        from bot.alert_sender import keyword_matches
        from bot.alert_site import _montar_mensagem, _site_link, enviar_alerta_site_para
        from bot.services import normalizar_whatsapp, trocar_links_loja_por_site

        promo = Promo.objects.filter(pk=options['promo']).first()
        if not promo:
            raise CommandError(f"Promo {options['promo']} não encontrada.")

        numero = normalizar_whatsapp(options['whatsapp'])
        texto = promo.texto_original or promo.titulo
        base_site = _site_link()
        promo_url = f'{base_site}/promos/{promo.pk}/{promo.slug}/'
        texto_site = trocar_links_loja_por_site(texto, promo.pk, base_site) or texto
        if f'/promos/{promo.pk}/' not in texto_site:
            texto_site = f'{texto_site.rstrip()}\n\n🛒 Ver oferta: {promo_url}'

        foto = promo.imagem_url or None
        if foto and foto.startswith('/'):
            foto = base_site + foto

        alertas = list(AlertaSite.objects.filter(is_active=True, whatsapp=numero))
        alerta = None
        if options['keyword']:
            alerta = next(
                (a for a in alertas if a.keyword.casefold() == options['keyword'].casefold()),
                None,
            )
        if not alerta:
            alerta = next((a for a in alertas if keyword_matches(texto, a.keyword)), None)

        if alerta:
            nome = options['nome'] or alerta.nome
            keyword = options['keyword'] or alerta.keyword
            token = alerta.token or None
        else:
            nome = options['nome'] or ''
            keyword = options['keyword'] or (promo.titulo or '')[:80]
            token = None
            self.stdout.write(self.style.WARNING(
                'Nenhum AlertaSite ativo combina com a oferta; enviando sem vínculo/cancelamento.'
            ))

        mensagem = _montar_mensagem(nome, keyword, texto_site, base_site, token)

        self.stdout.write(f'Promo {promo.pk} — {promo.titulo[:80]}')
        self.stdout.write(f'Destino: {numero}')
        self.stdout.write(f'Alerta: {alerta.pk if alerta else "-"} | keyword: {keyword}')

        if options['dry_run']:
            self.stdout.write('--- MENSAGEM (dry-run) ---')
            self.stdout.write(mensagem)
            return

        ok = enviar_alerta_site_para(
            numero, nome, keyword, texto,
            photo_path=foto, offer_text_site=texto_site, token=token,
        )
        if not ok:
            raise CommandError('Falha ao enviar o André Alerta (veja o log).')

        if alerta:
            alerta.last_sent_at = timezone.now()
            alerta.save(update_fields=['last_sent_at'])
        self.stdout.write(self.style.SUCCESS(f'André Alerta enviado para {numero}.'))
