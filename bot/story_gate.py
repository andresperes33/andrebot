import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Intervalo mínimo entre Stories (em minutos)
INTERVALO_MIN_MINUTOS = 30
# Janela de publicação: das 08:00 às 23:00
HORA_INICIO = 8
HORA_FIM = 23


def _agora():
    return datetime.now()


def dentro_da_janela(agora=None):
    """Retorna True se agora está dentro da janela de publicação (08:00-23:00)."""
    agora = agora or _agora()
    return HORA_INICIO <= agora.hour < HORA_FIM


def _ler_ultima_publicacao():
    """Lê o timestamp da última publicação do Story (persistido no banco)."""
    try:
        from django.db import close_old_connections
        close_old_connections()
        from bot.models import BotConfig
        valor = BotConfig.get('ultima_publicacao_ig', '')
        if valor:
            return datetime.fromisoformat(valor)
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível ler última publicação IG: {e}")
    return None


def _salvar_ultima_publicacao(agora=None):
    """Persiste o timestamp da última publicação do Story."""
    agora = agora or _agora()
    try:
        from django.db import close_old_connections
        close_old_connections()
        from bot.models import BotConfig
        BotConfig.set('ultima_publicacao_ig', agora.isoformat())
    except Exception as e:
        logger.error(f"❌ Erro ao persistir última publicação IG: {e}")


def pode_publicar_story(agora=None):
    """
    Decide se um Story pode ser publicado agora, respeitando:
    - Janela de horário (08:00 às 23:00)
    - Intervalo mínimo de 30 minutos desde o último
    Retorna (permitido: bool, motivo: str).
    """
    agora = agora or _agora()

    if not dentro_da_janela(agora):
        return False, f"fora da janela ({HORA_INICIO}h-{HORA_FIM}h)"

    ultima = _ler_ultima_publicacao()
    if ultima:
        decorrido_min = (agora - ultima).total_seconds() / 60
        if decorrido_min < INTERVALO_MIN_MINUTOS:
            faltam = INTERVALO_MIN_MINUTOS - decorrido_min
            return False, f"cooldown de {INTERVALO_MIN_MINUTOS} min (faltam {faltam:.0f} min)"

    return True, "ok"


def registrar_publicacao(agora=None):
    """Registra que um Story foi publicado agora (atualiza o cooldown)."""
    agora = agora or _agora()
    _salvar_ultima_publicacao(agora)
