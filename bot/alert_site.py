"""
Dispara alertas do NITRO ALERTA (site) para o WhatsApp dos usuários cadastrados.
Reaproveita a mesma lógica de matching de palavras-chave do bot do Telegram.
"""
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def send_alerts_site(offer_text: str, photo_path=None):
    """
    Percorre os alertas cadastrados no site (AlertaSite) e envia a oferta
    para o WhatsApp de cada usuário cuja palavra-chave combina.
    Envia sempre que aparece (pode ser mais de uma vez por dia).
    """
    from bot.models import AlertaSite
    from bot.alert_sender import keyword_matches
    from bot.services import send_whatsapp_to_user, normalizar_whatsapp

    alertas = AlertaSite.objects.filter(is_active=True)
    if not alertas.exists():
        return

    site_link = getattr(settings, 'SITE_URL', 'https://www.nitrotech.store')

    for alerta in alertas:
        try:
            if not keyword_matches(offer_text, alerta.keyword):
                continue

            numero = normalizar_whatsapp(alerta.whatsapp)
            if not numero:
                continue

            mensagem = (
                f"🔔 *Nitro Tech Alerta*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{alerta.nome or 'Olá'}, o Nitro Tech Alerta acabou de encontrar o seu produto "
                f"*{alerta.keyword}*!\n\n"
                f"*Aqui está a oferta:*\n\n"
                f"{offer_text}\n\n"
                f"📲 Confira mais ofertas: {site_link}\n"
                f"────────────────\n"
                f"🔕 Para parar de receber, clique aqui: {site_link}/nitro-alerta/cancelar/{alerta.token}"
            )

            ok = send_whatsapp_to_user(numero, mensagem, image_path=photo_path)
            if ok:
                alerta.last_sent_at = timezone.now()
                alerta.save(update_fields=['last_sent_at'])
                logger.info(f"✅ Nitro Alerta enviado para {alerta.whatsapp} ({alerta.keyword})")
            else:
                logger.warning(f"⚠️ Nitro Alerta falhou para {alerta.whatsapp} ({alerta.keyword})")
        except Exception as e:
            logger.error(f"❌ Erro no Nitro Alerta {alerta.pk}: {e}")
