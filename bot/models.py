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


class AlertaSite(models.Model):
    """
    Alerta de produto por WhatsApp cadastrado no site (Nitro Alerta).
    Quando uma oferta que casa com a palavra-chave aparece, o site envia
    para o WhatsApp do usuário.
    """
    nome = models.CharField(max_length=100, blank=True, default='')
    whatsapp = models.CharField(max_length=20, db_index=True, help_text='Formato +55DDDNUMERO (gerado automaticamente).')
    keyword = models.CharField(max_length=200)
    token = models.CharField(max_length=64, blank=True, default='', db_index=True, help_text='Token único para cancelar o alerta pelo link.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Alerta do Site'
        verbose_name_plural = 'Alertas do Site'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.nome or self.whatsapp} → {self.keyword}"


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
        ('kit', 'Kit (Placa + CPU + RAM)'),
        ('notebook', 'Notebook'),
        ('monitor', 'Monitor'),
        ('celular', 'Celular / Smartphone'),
        ('tablet', 'Tablet'),
        ('tv', 'TV'),
        ('caixa_som', 'Caixa de Som / Soundbar'),
        ('headset', 'Fone / Headset'),
        ('teclado', 'Teclado'),
        ('mouse', 'Mouse'),
        ('mousepad', 'Mousepad'),
        ('cadeira', 'Cadeira Escritório / Gamer'),
        ('impressora', 'Impressora'),
        ('fonte', 'Fonte'),
        ('gabinete', 'Gabinete'),
        ('cooler', 'Cooler / Water Cooler / Fan'),
        ('pasta_termica', 'Pasta Térmica'),
        ('controle', 'Controle / Gamepad'),
        ('webcam', 'Webcam'),
        ('cabo', 'Cabo / Carregador'),
        ('microfone', 'Microfone'),
        ('roteador', 'Roteador'),
        ('console', 'Console'),
        ('jogo', 'Jogo'),
        ('cupom', 'Cupom'),
        ('ar_condicionado', 'Ar Condicionado'),
        ('outros', 'Outros'),
    ]

    titulo = models.CharField(max_length=500, blank=True)
    preco = models.CharField(max_length=100, blank=True)
    cupom = models.CharField(max_length=1000, blank=True)
    link_afiliado = models.CharField(max_length=2000)
    url_chave = models.CharField(max_length=1000, blank=True, db_index=True)
    produto_chave = models.CharField(max_length=1000, blank=True, db_index=True, help_text='Link normalizado (sem preço) que identifica o mesmo produto ao longo do tempo — usado no histórico de preços.')
    imagem_url = models.CharField(max_length=2000, blank=True)
    categoria = models.CharField(max_length=50, choices=CATEGORIA_CHOICES, default='outros')
    loja = models.CharField(max_length=50, blank=True, default='')
    fonte = models.CharField(max_length=100, default='zFinnY')
    texto_original = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Promoção'
        verbose_name_plural = 'Promoções'

    def __str__(self):
        return f"{self.titulo[:60]} — {self.preco} ({self.criado_em.strftime('%d/%m %H:%M')})"


class Artigo(models.Model):
    """
    Artigo/guiu original do site (conteúdo exclusivo para SEO e AdSense).
    """
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    categoria = models.CharField(max_length=50, blank=True, default='', db_index=True, help_text='Categoria do artigo (ex.: Celulares, Placas de Vídeo). Você define ao criar.')
    conteudo = models.TextField(help_text='Conteúdo em linha única (HTML) ou blocos separados por quebras. Recomenda-se usar tags básicas de HTML (<p>, <h2>, <ul>, <strong>).')
    produtos_texto = models.TextField(blank=True, help_text='Produtos recomendados na barra lateral. Uma linha por produto, no formato: Nome do produto | Loja: https://link | Loja2: https://link2. Ex.: "GameSir Nova Lite | AliExpress: https://s.click.aliexpress.com/x | Shopee: https://s.shopee.com.br/x"')
    imagem = models.ImageField(upload_to='artigos/', blank=True, help_text='Imagem de capa do artigo. Enviada em JPG/PNG e convertida automaticamente para WebP.')
    publicado = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Artigo'
        verbose_name_plural = 'Artigos'

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        # Converte a imagem enviada para WebP (otimização de carregamento/SEO).
        if self.imagem:
            try:
                self.imagem = self._converter_webp(self.imagem)
            except Exception as e:
                print(f"[Artigo] Erro ao converter imagem para WebP: {e}")
        # Converte links "crus" da barra lateral de produtos para os links de
        # afiliado (Amazon, Shopee, Mercado Livre, AliExpress, etc.). O usuário
        # cola o link normal no admin e o sistema já salva o de afiliado.
        if self.produtos_texto:
            try:
                from bot.services import _converter_links_afiliado_texto
                self.produtos_texto = _converter_links_afiliado_texto(self.produtos_texto)
            except Exception as e:
                print(f"[Artigo] Erro ao converter links de produtos: {e}")
        super().save(*args, **kwargs)

    def _converter_webp(self, imagem):
        """
        Converte a imagem para WebP (qualidade 82, redimensiona para o máximo
        de 1200px de largura), preservando o formato de arquivo .webp.
        """
        from io import BytesIO
        from PIL import Image
        from django.core.files.base import ContentFile

        img = Image.open(imagem)
        img = img.convert('RGB')

        mime = getattr(imagem, 'content_type', '') or ''
        formato_orig = (imagem.name or '').lower().rsplit('.', 1)[-1] if '.' in (imagem.name or '') else 'jpg'

        # Nome base do arquivo, sem a extensão antiga
        base = (imagem.name or 'artigo').rsplit('.', 1)[0]

        # Redimensiona se for muito larga
        width, height = img.size
        if width > 1200:
            nova_altura = int(height * (1200 / width))
            img = img.resize((1200, nova_altura), Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format='WEBP', quality=82, method=6)
        buf.seek(0)

        novo_nome = f"{base}.webp"
        return ContentFile(buf.read(), name=novo_nome)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('blog_artigo', args=[self.slug])


class Evento(models.Model):
    """
    Quadro de Eventos: promoções/produtos em destaque que o usuário quer
    publicar em local estratégico do site. Tem imagem, título e conteúdo.
    """
    titulo = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    conteudo = models.TextField(help_text='Conteúdo do evento (HTML). Recomenda-se usar tags básicas (<p>, <h2>, <ul>, <strong>).')
    imagem = models.ImageField(upload_to='eventos/', blank=True, help_text='Imagem do evento. Enviada em JPG/PNG e convertida automaticamente para WebP.')
    publicado = models.BooleanField(default=True)
    destaque = models.BooleanField(default=False, help_text='Se marcado, aparece em destaque no topo da página de Promoções.')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Evento'
        verbose_name_plural = 'Quadro de Eventos'

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        # Converte a imagem enviada para WebP (otimização de carregamento/SEO).
        if self.imagem:
            try:
                self.imagem = self._converter_webp(self.imagem)
            except Exception as e:
                print(f"[Evento] Erro ao converter imagem para WebP: {e}")
        super().save(*args, **kwargs)

    def _converter_webp(self, imagem):
        """Converte a imagem para WebP (qualidade 82, redimensiona para no
        máximo 1200px de largura), preservando o formato .webp."""
        from io import BytesIO
        from PIL import Image
        from django.core.files.base import ContentFile

        img = Image.open(imagem)
        img = img.convert('RGB')
        base = (imagem.name or 'evento').rsplit('.', 1)[0]

        width, height = img.size
        if width > 1200:
            nova_altura = int(height * (1200 / width))
            img = img.resize((1200, nova_altura), Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format='WEBP', quality=82, method=6)
        buf.seek(0)

        novo_nome = f"{base}.webp"
        return ContentFile(buf.read(), name=novo_nome)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('evento_detail', args=[self.slug])


class ComentarioArtigo(models.Model):
    """
    Comentário de visitante em um artigo do blog.
    """
    artigo = models.ForeignKey(Artigo, on_delete=models.CASCADE, related_name='comentarios')
    nome = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    texto = models.TextField()
    publicado = models.BooleanField(default=False, help_text='Comentários ficam invisíveis até serem aprovados.')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['criado_em']
        verbose_name = 'Comentário'
        verbose_name_plural = 'Comentários'

    def __str__(self):
        return f"{self.nome} — {self.artigo.titulo}"
