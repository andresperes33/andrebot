import re
import unicodedata
from django.db import migrations

# Mesmas listas/função de bot.services._chave_produto (cópia para a migration
# ser autossuficiente, como as demais).
_TOKENS_RUIDO = {
    'novo', 'nova', 'original', 'novos', 'novas',
    'promoção', 'promocao', 'promo', 'oferta', 'imperdível', 'imperdivel',
    'barato', 'barata', 'desconto',
}
_TOKENS_TIPO = {
    'console', 'videogame', 'video', 'game', 'gamer', 'kit', 'combo',
    'pacote', 'oficial', 'padrao', 'standard', 'novo', 'nova',
}
_PREFIXOS_LOJA = {
    'aliexpress', 'mercadolivre', 'mercado', 'livre', 'amazon', 'shopee',
    'magalu', 'magazine', 'luiza', 'kabum', 'pichau', 'terabyte',
    'americanas', 'casas', 'bahia', 'walmart', 'fast', 'shop', 'renner',
    'submarino', 'pontofrio', 'ponto', 'cnc', 'seller',
}


def _chave_produto(titulo):
    if not titulo:
        return ''
    t = unicodedata.normalize('NFKD', titulo).encode('ascii', 'ignore').decode('ascii')
    t = re.sub(r'[^\w\s.,!?/-]', ' ', t).lower()
    palavras = t.split()
    limpas = []
    for w in palavras:
        if w in _TOKENS_RUIDO:
            continue
        if w in _TOKENS_TIPO:
            continue
        if w in _PREFIXOS_LOJA:
            continue
        if re.fullmatch(r'\d{2,4}w', w):
            continue
        if re.fullmatch(r'\d{2,4}hz', w):
            continue
        if re.fullmatch(r'\d+x', w):
            continue
        if w in ('bluetooth', 'wireless', 'sem', 'fio', 'rgb'):
            continue
        if not re.search(r'\w', w):
            continue
        limpas.append(w)
    chave = ' '.join(limpas).strip()
    chave = re.sub(r'\s+', ' ', chave)
    return chave


def backfill_nome(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        chave = _chave_produto(promo.titulo)
        if not chave:
            # fallback: tenta do texto original (primeira linha com cara de título)
            primera = (promo.texto_original or '').split('\n')[0]
            chave = _chave_produto(primera)
        if chave:
            promo.produto_chave = chave
            promo.save(update_fields=['produto_chave'])


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0024_backfill_produto_chave'),
    ]

    operations = [
        migrations.RunPython(backfill_nome, migrations.RunPython.noop),
    ]
