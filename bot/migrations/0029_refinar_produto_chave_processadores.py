import re
import unicodedata
from django.db import migrations

_TOKENS_RUIDO = {
    'novo', 'nova', 'original', 'novos', 'novas',
    'promoção', 'promocao', 'promo', 'oferta', 'imperdível', 'imperdivel',
    'barato', 'barata', 'desconto',
    'vendido', 'venda', 'por', 'para', 'com', 'da', 'do', 'de', 'em',
    'controle', 'branco', 'branca', 'preto', 'preta', 'cinza', 'rosa',
    'azul', 'vermelho', 'dourado', 'prata', 'sony', 'xbox', 'nintendo',
}
_TOKENS_TIPO = {
    'console', 'videogame', 'video', 'game', 'gamer', 'kit', 'combo',
    'pacote', 'oficial', 'padrao', 'standard', 'novo', 'nova', 'jogo',
    'jogos', 'edicao', 'edition', 'pre', 'venda', 'langamento',
    'lancamento', 'importado', 'digital', 'fisico', 'fisica', 'midia',
    'cpu', 'processador', 'amd', 'nucleos', 'nucleo', 'nucleus',
}
_TOKENS_GENERICOS = {
    'ddr3', 'ddr4', 'ddr5', 'am3', 'am4', 'am5', 'lga', 'socket',
    'r3', 'r5', 'r7', 'r9', 'gen', 'series',
}
_PLATAFORMAS = {
    'series', 'one', 'steam', 'pc', 'pcgamer', 'epic', 'uu', 'redeem',
}
_PREFIXOS_LOJA = {
    'aliexpress', 'mercadolivre', 'mercado', 'livre', 'amazon', 'shopee',
    'magalu', 'magazine', 'luiza', 'kabum', 'pichau', 'terabyte',
    'americanas', 'casas', 'bahia', 'walmart', 'fast', 'shop', 'renner',
    'submarino', 'pontofrio', 'ponto', 'cnc', 'seller',
}
_ALIASES = [
    (r'\bgrand\s*theft\s*auto\s+(?:vi|6)\b', 'gta6'),
    (r'\bgrand\s*theft\s*auto\s+v\b', 'gta5'),
    (r'\bgta\s+(?:vi|6)\b', 'gta6'),
    (r'\bgta\s+5\b', 'gta5'),
    (r'\bgod\s+of\s+war\s+:?\s+ragnarok\b', 'gow ragnarok'),
    (r'\bplaystation\s*(?:5|5\s*pro|slim)\b', 'ps5'),
    (r'\bplaystation\s*4\b', 'ps4'),
    (r'\bplaystation\b', 'ps5'),
]


def _chave_produto(titulo):
    if not titulo:
        return ''
    t = unicodedata.normalize('NFKD', titulo).encode('ascii', 'ignore').decode('ascii')
    t = re.sub(r'[^\w\s.,!?/]', ' ', t).lower()
    for pat, cano in _ALIASES:
        t = re.sub(pat, cano, t)
    palavras = t.split()
    limpas = []
    for w in palavras:
        if w in _TOKENS_RUIDO or w in _TOKENS_TIPO or w in _TOKENS_GENERICOS:
            continue
        if w in _PLATAFORMAS or w in _PREFIXOS_LOJA:
            continue
        if re.fullmatch(r'\d{2,4}w', w) or re.fullmatch(r'\d{2,4}hz', w):
            continue
        if re.fullmatch(r'\d{1,2}x', w):
            continue
        if re.fullmatch(r'\d{2,4}gb', w) or re.fullmatch(r'\d{2,4}tb', w):
            continue
        if re.fullmatch(r'\d{1,2}', w) or w in ('1000',):
            continue
        if w in ('bluetooth', 'wireless', 'sem', 'fio', 'rgb'):
            continue
        if re.fullmatch(r'\(\d+\)', w):
            continue
        if not re.search(r'\w', w):
            continue
        limpas.append(w)
    vistos = set()
    unicos = []
    for w in limpas:
        if w not in vistos:
            vistos.add(w)
            unicos.append(w)
    chave = ' '.join(unicos).strip()
    chave = re.sub(r'\s+', ' ', chave)
    return chave


def backfill(apps, schema_editor):
    from bot.classifier import detectar_categoria
    from bot.services import _linha_titulo
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        texto = promo.texto_original or promo.titulo
        titulo = _linha_titulo(texto)
        nova = detectar_categoria(texto, titulo=titulo)
        if nova and nova != promo.categoria:
            promo.categoria = nova
        chave = _chave_produto(promo.titulo)
        if not chave:
            chave = _chave_produto(titulo)
        if chave:
            promo.produto_chave = chave
        promo.save(update_fields=['categoria', 'produto_chave'])


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0028_refinar_produto_chave_consoles'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
