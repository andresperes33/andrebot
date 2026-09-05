from django.contrib import admin
from .models import UserAlert, BotConfig, Promo, Artigo, AlertaSite, Evento, ComentarioArtigo



@admin.register(UserAlert)
class UserAlertAdmin(admin.ModelAdmin):
    list_display = ('telegram_first_name', 'telegram_user_id', 'keyword', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('telegram_first_name', 'keyword')


@admin.register(BotConfig)
class BotConfigAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'updated_at')


@admin.register(Promo)
class PromoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'preco', 'cupom', 'categoria', 'fonte', 'criado_em')
    list_filter = ('categoria', 'fonte', 'criado_em')
    search_fields = ('titulo', 'cupom', 'texto_original')
    readonly_fields = ('criado_em', 'produto_chave')
    ordering = ('-criado_em',)


@admin.register(Artigo)
class ArtigoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'categoria', 'slug', 'publicado', 'criado_em')
    list_filter = ('publicado', 'categoria')
    search_fields = ('titulo', 'conteudo', 'categoria', 'produtos_texto')
    prepopulated_fields = {'slug': ('titulo',)}
    ordering = ('-criado_em',)
    fieldsets = (
        (None, {'fields': ('titulo', 'slug', 'categoria', 'imagem', 'conteudo', 'publicado')}),
        ('Barra lateral de produtos', {'fields': ('produtos_texto',), 'description': 'Uma linha por produto, no formato: <strong>Nome do produto | Loja: https://link | Loja2: https://link2</strong>. Ex.: "GameSir Nova Lite | AliExpress: https://s.click.aliexpress.com/x | Shopee: https://s.shopee.com.br/x"'})
    )


@admin.register(AlertaSite)
class AlertaSiteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'whatsapp', 'keyword', 'is_active', 'last_sent_at', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('nome', 'whatsapp', 'keyword')
    ordering = ('-created_at',)


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'publicado', 'destaque', 'criado_em')
    list_filter = ('publicado', 'destaque')
    search_fields = ('titulo', 'conteudo')
    prepopulated_fields = {'slug': ('titulo',)}
    ordering = ('-criado_em',)
    list_editable = ('publicado', 'destaque')


@admin.register(ComentarioArtigo)
class ComentarioArtigoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'artigo', 'publicado', 'criado_em')
    list_filter = ('publicado', 'artigo', 'criado_em')
    search_fields = ('nome', 'email', 'texto')
    list_editable = ('publicado',)
    ordering = ('-criado_em',)
