from django.contrib import admin
from django import forms
from .models import UserAlert, BotConfig, Promo, Artigo


# Chave no BotConfig que guarda a lista de categorias do blog (uma por linha).
BLOG_CATEGORIAS_KEY = 'blog_categorias'

# Categorias padrão, caso o usuário ainda não tenha configurado.
_CATEGORIAS_PADRAO = ['Celulares', 'Placas de Vídeo', 'Periféricos', 'Hardware', 'Guias']


def _categorias_do_blog():
    """Lê a lista de categorias do Blog configurada no BotConfig."""
    valor = BotConfig.get(BLOG_CATEGORIAS_KEY, '')
    if not valor:
        return _CATEGORIAS_PADRAO
    return [l.strip() for l in valor.split('\n') if l.strip()]


class ArtigoForm(forms.ModelForm):
    class Meta:
        model = Artigo
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categorias = _categorias_do_blog()
        choices = [('', '— Sem categoria —')] + [(c, c) for c in categorias]
        # Campo Categoria como dropdown com as opções do BotConfig
        self.fields['categoria'].widget = forms.Select(choices=choices)
        self.fields['categoria'].required = False


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
    form = ArtigoForm
    list_display = ('titulo', 'categoria', 'slug', 'publicado', 'criado_em')
    list_filter = ('publicado', 'categoria')
    search_fields = ('titulo', 'conteudo', 'categoria')
    prepopulated_fields = {'slug': ('titulo',)}
    ordering = ('-criado_em',)
