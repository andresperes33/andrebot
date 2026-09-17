import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Intervalo mínimo entre Stories (em minutos)
INTERVALO_MIN_MINUTOS = 45


def _agora():
    return datetime.now()


def _ler_ultima_publicacao(chave='ultima_publicacao_ig'):
    """Lê o timestamp da última publicação (persistido no banco)."""
    try:
        from django.db import close_old_connections
        close_old_connections()
        from bot.models import BotConfig
        valor = BotConfig.get(chave, '')
        if valor:
            return datetime.fromisoformat(valor)
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível ler última publicação ({chave}): {e}")
    return None


def _salvar_ultima_publicacao(agora=None, chave='ultima_publicacao_ig'):
    """Persiste o timestamp da última publicação."""
    agora = agora or _agora()
    try:
        from django.db import close_old_connections
        close_old_connections()
        from bot.models import BotConfig
        BotConfig.set(chave, agora.isoformat())
    except Exception as e:
        logger.error(f"❌ Erro ao persistir última publicação ({chave}): {e}")


def pode_publicar_story(agora=None, chave='ultima_publicacao_ig'):
    """
    Decide se uma publicação pode ser feita agora, respeitando apenas o
    intervalo mínimo de 30 minutos desde a última (sem janela de horário).
    Retorna (permitido: bool, motivo: str).
    """
    agora = agora or _agora()

    ultima = _ler_ultima_publicacao(chave)
    if ultima:
        decorrido_min = (agora - ultima).total_seconds() / 60
        if decorrido_min < INTERVALO_MIN_MINUTOS:
            faltam = INTERVALO_MIN_MINUTOS - decorrido_min
            return False, f"cooldown de {INTERVALO_MIN_MINUTOS} min (faltam {faltam:.0f} min)"

    return True, "ok"


def registrar_publicacao(agora=None, chave='ultima_publicacao_ig'):
    """Registra que uma publicação foi feita agora (atualiza o cooldown)."""
    agora = agora or _agora()
    _salvar_ultima_publicacao(agora, chave)
