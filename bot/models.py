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


class BotConfig(models.Model):
    """
    Armazena configurações persistentes do bot no banco de dados.
    Persiste entre deploys (diferente de arquivos JSON locais).
    """
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do Bot"

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value):
        cls.objects.update_or_create(key=key, defaults={'value': str(value)})


class Promo(models.Model):
    """
    Armazena cada promoção detectada pelo bot monitor.
    Alimenta a página pública de promos.
    """
    CATEGORIA_CHOICES = [
        ('ssd', 'SSD / HD'),
        ('placa_video', 'Placa de Vídeo'),
        ('placa_mae', 'Placa-mãe'),
        ('processador', 'Processador'),
        ('memoria_ram', 'Memória RAM'),
        ('notebook', 'Notebook'),
        ('monitor', 'Monitor'),
        ('celular', 'Celular / Smartphone'),
        ('tv', 'TV'),
        ('headset', 'Fone / Headset'),
        ('teclado', 'Teclado'),
        ('mouse', 'Mouse'),
        ('cadeira', 'Cadeira Gamer'),
        ('impressora', 'Impressora'),
        ('outros', 'Outros'),
    ]

    titulo = models.CharField(max_length=500, blank=True)
    preco = models.CharField(max_length=100, blank=True)
    cupom = models.CharField(max_length=200, blank=True)
    link_afiliado = models.URLField(max_length=2000)
    imagem_url = models.URLField(max_length=2000, blank=True)
    categoria = models.CharField(max_length=50, choices=CATEGORIA_CHOICES, default='outros')
    fonte = models.CharField(max_length=100, default='zFinnY')
    texto_original = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Promoção'
        verbose_name_plural = 'Promoções'

    def __str__(self):
        return f"{self.titulo[:60]} — {self.preco} ({self.criado_em.strftime('%d/%m %H:%M')})"
