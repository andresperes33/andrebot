from django.db import models


class UserAlert(models.Model):
    """
    Armazena as palavras-chave de alerta de cada usuário do Telegram.
    """
    telegram_user_id = models.BigIntegerField(db_index=True)
    telegram_username = models.CharField(max_length=100, blank=True, null=True)
    telegram_first_name = models.CharField(max_length=100, blank=True, null=True)
    keyword = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('telegram_user_id', 'keyword')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.telegram_first_name} ({self.telegram_user_id}) → {self.keyword}"
