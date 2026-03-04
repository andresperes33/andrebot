"""
Função utilitária para enviar alertas de promoções
para os usuários que possuem palavras-chave compatíveis.
Chamada pelo monitor_offers.py após cada nova promo publicada.
"""
import logging
import requests as http_requests
from django.conf import settings

logger = logging.getLogger(__name__)


def keyword_matches(offer_text: str, keyword: str) -> bool:
    """
    Verifica se o texto da oferta corresponde à palavra-chave do usuário.

    Lógica:
      +  →  E  (todos os termos separados por + devem estar presentes)
      /  →  OU (pelo menos um dos termos separados por / deve estar presente)

    Exemplo: "samsung+s23/s24/s25"
    → Deve conter "samsung" E pelo menos um de ("s23", "s24", "s25")
    """
    text_lower = offer_text.lower()
    keyword_lower = keyword.lower()

    # Divide pelos termos obrigatórios (+)
    required_groups = keyword_lower.split('+')

    for group in required_groups:
        # Dentro de cada grupo, qualquer uma das opções (/) serve
        options = group.split('/')
        if not any(opt.strip() in text_lower for opt in options if opt.strip()):
            return False
    return True


def send_alerts(offer_text: str, photo_path: str = None):
    """
    Verifica os alertas cadastrados e envia mensagem para cada usuário
    cuja palavra-chave combina com a oferta.
    """
    from bot.models import UserAlert

    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not bot_token:
        logger.warning("send_alerts: TELEGRAM_BOT_TOKEN não configurado.")
        return

    alerts = UserAlert.objects.filter(is_active=True)
    if not alerts.exists():
        return

    notified_users = set()

    for alert in alerts:
        user_id = alert.telegram_user_id

        # Evita mandar duplicata para o mesmo usuário (com keywords diferentes que batem)
        if user_id in notified_users:
            continue

        if keyword_matches(offer_text, alert.keyword):
            notified_users.add(user_id)
            try:
                header = (
                    f"🔔 *Alerta para:* `{alert.keyword}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                )
                full_text = header + offer_text

                if photo_path and __import__('os').path.exists(photo_path):
                    # Envia com foto
                    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                    with open(photo_path, 'rb') as img:
                        resp = http_requests.post(url, data={
                            'chat_id': user_id,
                            'caption': full_text[:1024],
                            'parse_mode': 'Markdown'
                        }, files={'photo': img}, timeout=20)
                else:
                    # Envia só texto
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    resp = http_requests.post(url, json={
                        'chat_id': user_id,
                        'text': full_text[:4096],
                        'parse_mode': 'Markdown'
                    }, timeout=10)

                if resp.status_code == 200:
                    logger.info(f"✅ Alerta enviado para {user_id} ({alert.keyword})")
                else:
                    logger.warning(f"⚠️ Erro ao enviar alerta para {user_id}: {resp.text[:100]}")

            except Exception as e:
                logger.error(f"❌ Exceção ao enviar alerta para {user_id}: {e}")
