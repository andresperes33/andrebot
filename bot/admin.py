from django.contrib import admin
from .models import UserAlert, BotConfig, Promo


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
    readonly_fields = ('criado_em',)
    ordering = ('-criado_em',)
