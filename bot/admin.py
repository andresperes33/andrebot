from django.contrib import admin
from .models import UserAlert, BotConfig, Promo, Artigo, AlertaSite



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
    search_fields = ('titulo', 'conteudo', 'categoria')
    prepopulated_fields = {'slug': ('titulo',)}
    ordering = ('-criado_em',)


@admin.register(AlertaSite)
class AlertaSiteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'whatsapp', 'keyword', 'is_active', 'last_sent_at', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('nome', 'whatsapp', 'keyword')
    ordering = ('-created_at',)
