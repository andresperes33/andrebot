import re
import time
import os
import hashlib
import json
import urllib.parse
import unicodedata
import requests
from django.conf import settings


def site_base_url(request):
    """URL base do site, sempre em HTTPS (mesmo atrás de proxy/Cloudflare)."""
    url = request.build_absolute_uri('/')
    if url.startswith('http://'):
        url = 'https://' + url[len('http://'):]
    return url.rstrip('/')

# Rodapé de canais anexado às promoções (Telegram/WhatsApp/site). Em texto puro.
_RODAPE_CANAIS_TEXTO = (
    "\n\n"
    "📲 Canais André Indica:\n"
    "📢 Telegram: https://t.me/Nitro_Tech_1\n"
    "💬 WhatsApp: https://chat.whatsapp.com/Jxjt68Mfr9J4tx1vIS82DD\n"
    "🤖 Bot: https://t.me/alertas_andre_bot\n"
    "🌐 Site: https://promos.andreindicatech.com.br\n"
    "📸 Instagram: https://www.instagram.com/andreindicatech/\n"
    "🎵 TikTok: https://www.tiktok.com/@andreperes.dev\n"
    "📘 Facebook: https://www.facebook.com/profile.php?id=100069882953168\n"
    "\n"
    "⚠️ Aviso: as ofertas são geradas automaticamente e podem conter erros. "
    "Confirme preço e disponibilidade na loja antes de comprar."
)

# Mesmo rodapé em HTML pro Telegram (parse_mode='html'): link embutido no texto.
_RODAPE_CANAIS_TG_HTML = (
    "\n\n"
    "📲 Canais André Indica:\n"
    '📢 <a href="https://t.me/Nitro_Tech_1">Grupo no Telegram</a>\n'
    '💬 <a href="https://chat.whatsapp.com/Jxjt68Mfr9J4tx1vIS82DD">Grupo no WhatsApp</a>\n'
    '🤖 <a href="https://t.me/alertas_andre_bot">Bot André Indica</a>\n'
    '🌐 <a href="https://promos.andreindicatech.com.br">Site / App</a>\n'
    '📸 <a href="https://www.instagram.com/andreindicatech/">Instagram</a>\n'
    '🎵 <a href="https://www.tiktok.com/@andreperes.dev">TikTok</a>\n'
    '📘 <a href="https://www.facebook.com/profile.php?id=100069882953168">Facebook</a>\n'
    "\n"
    "⚠️ Aviso: as ofertas são geradas automaticamente e podem conter erros. "
    "Confirme preço e disponibilidade na loja antes de comprar."
)

# Mesmo rodapé em HTML, com links clicáveis (usado na página do produto).
_RODAPE_CANAIS_HTML = """
<div class="detail-channels">
    <div class="detail-label">📲 Canais André Indica</div>
    <a href="https://t.me/Nitro_Tech_1" target="_blank" rel="noopener">📢 Grupo no Telegram</a>
    <a href="https://chat.whatsapp.com/Jxjt68Mfr9J4tx1vIS82DD" target="_blank" rel="noopener">💬 Grupo no WhatsApp</a>
    <a href="https://t.me/alertas_andre_bot" target="_blank" rel="noopener">🤖 Bot André Indica</a>
    <a href="https://promos.andreindicatech.com.br" target="_blank" rel="noopener">🌐 Site / App</a>
    <a href="https://www.instagram.com/andreindicatech/" target="_blank" rel="noopener">📸 Instagram</a>
    <a href="https://www.tiktok.com/@andreperes.dev" target="_blank" rel="noopener">🎵 TikTok</a>
    <a href="https://www.facebook.com/profile.php?id=100069882953168" target="_blank" rel="noopener">📘 Facebook</a>
</div>
<p class="detail-channels-aviso" style="margin-top:12px;font-size:13px;color:var(--mute);">
    📲 Comprando pelo app da loja o valor final pode sair MAIS BARATO! Muitas lojas liberam cupons, moedas e descontos exclusivos só no aplicativo. Vale conferir antes de finalizar a compra.
</p>
<p class="detail-channels-aviso" style="margin-top:6px;font-size:13px;color:var(--mute);">
    ⚠️ Aviso: as ofertas são geradas automaticamente e podem conter erros. Confirme preço e disponibilidade na loja antes de comprar.
</p>
"""


def _normalizar_url(url):
    """Normaliza uma URL de produto em uma chave estável para deduplicação."""
    url = (url or '').strip().rstrip('.,;|)')
    url = re.split(r'[?#]', url)[0]
    url = re.sub(r'^https?://', '', url, flags=re.I)
    url = re.sub(r'^www\.', '', url, flags=re.I)
    url = url.rstrip('/')
    return url.lower()


def cortar_rodape_imagem(caminho, rodape_px=10):
    """
    Corta `rodape_px` pixels da base da imagem (rodapé/crédito da postagem).
    Edita o arquivo in-place. Se algo falhar, mantém a imagem original.
    """
    try:
        from PIL import Image
        if not caminho or not os.path.exists(caminho):
            return caminho
        img = Image.open(caminho)
        largura, altura = img.size
        if rodape_px <= 0 or rodape_px >= altura:
            img.close()
            return caminho
        area = (0, 0, largura, altura - rodape_px)
        rend = img.crop(area)

        # Preserva o formato original (PNG mantém transparência; JPEG/JPG mexer de novo).
        formato = (img.format or 'JPEG').upper()
        if formato == 'PNG':
            rend.save(caminho, 'PNG')
        elif formato in ('JPEG', 'JPG'):
            rend.convert('RGB').save(caminho, 'JPEG', quality=95)
        else:
            rend.convert('RGB').save(caminho, 'JPEG', quality=95)

        img.close()
        print(f"🖼️ Rodapé cortado ({rodape_px}px, {formato}) em {caminho}")
        return caminho
    except Exception as err:
        print(f"Erro ao cortar rodapé da imagem: {err}")
        return caminho


def adicionar_watermark(caminho, texto='Andre Indica', escala=1.0):
    """
    Insere uma marca d'água com `texto` no canto inferior esquerdo da imagem,
    na mesma posição relativa do logo removido (esquerda ~1.6% da largura,
    base ~90.4% da altura). Edita o arquivo in-place. Se algo falhar, mantém
    a imagem original.

    Usa as cores do design system (NVIDIA Green #76b900 + contorno preto).
    `escala` multiplica o tamanho da fonte (base = 4.8% da altura da imagem).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        if not caminho or not os.path.exists(caminho):
            return caminho
        img = Image.open(caminho).convert('RGB')
        largura, altura = img.size

        # Tamanho proporcional à altura (base ~4.8% da altura, ajustável por escala)
        tamanho_fonte = max(10, int(altura * 0.048 * escala))
        try:
            fonte = ImageFont.load_default(size=tamanho_fonte)
        except TypeError:
            fonte = ImageFont.load_default()

        draw = ImageDraw.Draw(img)

        # Posição relativa: mesma do logo antigo (esquerda ~1.6% / base ~90.4%)
        x = int(largura * 0.016)
        base_y = int(altura * 0.904)
        y = base_y - tamanho_fonte

        # Cores do design system: verde André Indica (#76b900) com contorno preto
        verde_marca = (118, 185, 0)   # #76b900 (--primary)
        contorno = (0, 0, 0)          # preto (--on-primary)
        # Contorno (offsets ao redor) para legibilidade em qualquer fundo
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (1, -1), (-1, 1), (1, 1)):
            draw.text((x + dx, y + dy), texto, font=fonte, fill=contorno)
        draw.text((x, y), texto, font=fonte, fill=verde_marca)

        formato = (img.format or 'JPEG').upper()
        if formato == 'PNG':
            img.save(caminho, 'PNG')
        else:
            img.save(caminho, 'JPEG', quality=95)

        img.close()
        print(f"💧 Marca d'água '{texto}' adicionada em {caminho}")
        return caminho
    except Exception as err:
        print(f"Erro ao adicionar marca d'água: {err}")
        return caminho


def remover_marca_dagua_verde(caminho, x_lim=0.55, y_inicio=0.70, y_fim=1.0,
                              limiar_branco=230, dilatar=8):
    """
    Remove o logo verde ('Ofertas TecnoArt') no canto inferior esquerdo.
    Detecta a marca pelo verde (HSV) e mascara o verde + a vizinhança próxima
    (contorno escuro e letras prateadas ficam colados no verde), preenchendo com
    a cor de fundo. Limitar à vizinhança evita apagar o produto. Edita in-place.
    Se falhar (cv2 ausente etc.), mantém a imagem original.
    """
    if not caminho or not os.path.exists(caminho):
        return caminho
    try:
        import cv2
        import numpy as np
    except Exception:
        print("cv2 não disponível — pulando remoção de marca d'água.")
        return caminho
    try:
        img = cv2.imread(caminho)  # BGR
        if img is None:
            return caminho
        h, w = img.shape[:2]

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        H = hsv[:, :, 0].astype(int)
        S = hsv[:, :, 1].astype(int)
        V = hsv[:, :, 2].astype(int)
        verde = (H >= 30) & (H <= 95) & (S > 40) & (V > 40)

        # Restringe à região inferior esquerda
        regiao = np.zeros((h, w), dtype=bool)
        ry0, ry1 = int(y_inicio * h), int(y_fim * h)
        rx0, rx1 = 0, int(x_lim * w)
        regiao[ry0:ry1, rx0:rx1] = True
        verde_reg = verde & regiao

        if int(verde_reg.sum()) == 0:
            return caminho

        # Marca = verde + vizinhança próxima (o contorno escuro e as letras
        # prateadas ficam colados no verde). Limitar à vizinhança evita apagar
        # o produto que porventura esteja perto (ex.: base da cadeira).
        mask = cv2.dilate(verde_reg.astype(np.uint8) * 255,
                          np.ones((3, 3), np.uint8), iterations=dilatar)
        # Inclui pixels não-brancos que estejam dentro dessa vizinhança
        mn = img.min(axis=2).astype(int)
        naobranco = mn < limiar_branco
        mask[~(naobranco | verde_reg)] = 0

        # Cor de fundo estimada pela moldura da imagem (as imagens de produto
        # do canal têm fundo claro/branco). Preenche a marca com o fundo em vez
        # de inpaint (inpaint deixava mancha cinza).
        moldura = np.concatenate([
            img[0:max(1, h // 100)].reshape(-1, 3),
            img[max(0, h - h // 100):].reshape(-1, 3),
            img[:, 0:max(1, w // 100)].reshape(-1, 3),
            img[:, max(0, w - w // 100):].reshape(-1, 3),
        ])
        cor_fundo = np.median(moldura, axis=0).astype(np.uint8)

        res = img.copy()
        res[mask > 0] = cor_fundo
        cv2.imwrite(caminho, res)
        print(f"🧽 Marca d'água verde removida em {caminho}")
        return caminho
    except Exception as err:
        print(f"Erro ao remover marca d'água verde: {err}")
        return caminho


def _primeiro_link_produto(texto):
    """Extrai o primeiro link de produto do texto (ignora links de rede social e serviços)."""
    for lnk in re.findall(r'(https?://\S+)', texto or ''):
        lnk = lnk.rstrip('.,;|)')
        if any(d in lnk for d in ['t.me/', 'linktr.ee', 'youtube', 'youtu.be', 'tecnan.com.br', 'links.andreindica']):
            continue
        # Ignora links internos de serviços (assinaturas, plataformas)
        if any(d in lnk for d in ['amazonprime', 'netflix', 'disney+', 'hbo+', 'spotify', 'apple.music', 'steam',
                                  'pago.com.br', 'asassinatura', 'assinatura', 'plus', 'prime', 'completed']):
            continue
        return lnk
    return ''


def _link_produto_compra(texto):
    """Extrai o link do PRODUTO (para o botão 'Comprar com desconto'),
    distinguindo-o dos links de cupom/bots/moedas quando ambos aparecem.

    O canal costuma publicar vários links: o do produto ('Link APP', 'Link PC',
    'Link do produto'), o de cupom ('Resgate o cupom: ...') e links de bots
    ('Bot de descontos', 'Bot de Moedas'). O link do produto é o que deve ir no
    botão de compra e definir a loja.
    """
    if not texto:
        return ''
    itens = []  # (rotulo, link) — o rótulo é o texto antes do link na linha
    for linha in texto.split('\n'):
        m = re.search(r'(https?://\S+)', linha)
        if not m:
            continue
        link = m.group(1).rstrip('.,;|)')
        rotulo = linha[:m.start()].strip().casefold()
        if any(d in link for d in ['t.me/', 'linktr.ee', 'youtube', 'youtu.be', 'tecnan.com.br', 'links.andreindica']):
            continue
        # Ignora links internos de serviços (assinaturas, plataformas)
        if any(d in link for d in ['amazonprime', 'netflix', 'disny+', 'hbo+', 'spotify', 'apple.music', 'steam',
                                  'pago.com.br', 'asassinatura', 'assinatura', 'plus', 'prime', 'completed']):
            continue
        itens.append((rotulo, link))

    if not itens:
        return _primeiro_link_produto(texto)

    # 1) Rótulo explícito de produto ('Link APP', 'Link PC', 'Link do produto',
    #    'Comprar', ...). No AliExpress o 'Link APP'/'Link PC' é o produto.
    for rotulo, link in itens:
        if any(marc in rotulo for marc in (
            'produto', 'comprar', 'compre', 'link app', 'link pc',
            'link da', 'link para', 'este link', 'link do',
        )):
            return link

    # 2) Ignora rótulos que não são do produto (bot, moedas, cupom, canal...)
    for rotulo, link in itens:
        if not any(marc in rotulo for marc in (
            'bot', 'moeda', 'desconto', 'cupom', 'canal', 'grupo',
        )):
            return link

    return itens[0][1]


# Domínios/marcadores de loja que devem virar link da página do site (no
# Telegram/WhatsApp). Só converte URLs REAIS (com http/https) — não toca no
# nome da loja no texto (ex.: '#Kabum', 'Mercado Livre', 'Shopee').
# '[^\s<>"\']*?' (zero ou mais) permite marcas logo após '://' (ex.: amzn.to).
_RE_LINKS_LOJA = re.compile(
    r'https?://[^\s<>"\']*?(?:amazon|amzn\.to|link\.amazon|aoferta|shopee|'
    r'mercadolivre|mercadolibre|meli\.la|aliexpress|s\.click\.ali|kabum|'
    r'magazineluiza|magalu|mgl\.io|pichau|terabyte|americanas|casasbahia|'
    r'pontofrio|submarino|cnc|fastshop|walmart|renner|extra)[^\s<>"\']*',
    re.IGNORECASE,
)


def trocar_links_loja_por_site(texto, promo_id, site_url=''):
    """Substitui os links de loja do texto (Amazon, Shopee, ML, AliExpress,
    etc.) pelo link da página da promoção no site.

    Assim, quem clica no link no Telegram/WhatsApp vai para a página do
    produto aqui no site, e de lá o botão 'Comprar' leva ao produto/afiliado.
    Links de redes sociais e do rodapé não são alterados.
    """
    if not texto or not promo_id:
        return texto
    if not site_url:
        site_url = getattr(settings, 'SITE_URL', '') or ''
    site_url = site_url.rstrip('/')
    if not site_url:
        return texto
    pagina = f"{site_url}/promos/{promo_id}/"
    # Substitui apenas os links de loja (sobras de pontuação colada são
    # mantidas fora do link).
    def _sub(m):
        return pagina
    novo = _RE_LINKS_LOJA.sub(_sub, texto)
    return novo


def _nome_loja_por_url(url):
    """Infere o nome da loja a partir do domínio, quando o rótulo não foi
    informado. Ex.: tidd.ly → KaBuM (Awin), meli.la → Mercado Livre."""
    if not url:
        return ''
    baixo = url.casefold()
    pares = [
        ('amazon', 'Amazon'), ('amzn.to', 'Amazon'), ('link.amazon', 'Amazon'),
        ('aoferta', 'Amazon'),
        ('shopee', 'Shopee'), ('s.shopee', 'Shopee'),
        ('mercadolivre', 'Mercado Livre'), ('mercadolibre', 'Mercado Livre'),
        ('meli.la', 'Mercado Livre'), ('mlstatic', 'Mercado Livre'),
        ('aliexpress', 'AliExpress'), ('s.click.ali', 'AliExpress'),
        ('kabum', 'KaBuM'), ('tidd.ly', 'KaBuM'), ('awin1.com', 'Awin'),
        ('magazineluiza', 'Magazine Luíza'), ('magalu', 'Magazine Luíza'), ('mgl.io', 'Magazine Luíza'),
        ('pichau', 'Pichau'), ('terabyte', 'Terabyte'), ('americanas', 'Americanas'),
        ('casasbahia', 'Casas Bahia'), ('pontofrio', 'Ponto'), ('submarino', 'Submarino'),
        ('walmart', 'Walmart'), ('renner', 'Renner'),
    ]
    for chave, nome in pares:
        if chave in baixo:
            return nome
    return ''


def _converter_links_afiliado_texto(texto):
    """Converte cada URL de loja do texto para o link de afiliado.

    Usado ao salvar o artigo (campo produtos_texto) no admin: o usuário cola o
    link 'cru' (ex.: https://amzn.to/x, https://s.shopee.com.br/y) e o sistema
    salva já convertido para o link de afiliado da Nitro Tech.
    """
    if not texto:
        return texto

    def _sub(m):
        url = m.group(0).rstrip('.,;:!?')
        # Não converte novamente se já for link de afiliado.
        if any(marc in url.casefold() for marc in ('tag=', 'matt_tool=', 'mat_click', 'affiliate', 'awin', '?p=')):
            return url
        try:
            conv = convert_to_affiliate_link(url)
            return conv or url
        except Exception:
            return url

    # Converte apenas URLs de loja conhecidas (Amazon, Shopee, ML, Ali, etc.)
    return _RE_LINKS_LOJA.sub(_sub, texto)


# Palavras genéricas ruído ao normalizar o nome do produto para a chave
# (repetem entre todas as ofertas e não identificam o produto).
_TOKENS_RUIDO = {
    'novo', 'nova', 'original', 'novos', 'novas',
    'promoção', 'promocao', 'promo', 'oferta', 'imperdível', 'imperdivel',
    'barato', 'barata', 'desconto',
    'vendido', 'venda', 'por', 'para', 'com', 'da', 'do', 'de', 'em',
    'controle', 'branco', 'branca', 'preto', 'preta', 'cinza', 'rosa',
    'azul', 'vermelho', 'dourado', 'prata', 'sony', 'xbox', 'nintendo',
}

# Palavras que identificam a categoria/tipo mas não o produto em si.
# Removidas para que 'Console Switch 2' e 'Switch 2' agrupem juntos.
_TOKENS_TIPO = {
    'console', 'videogame', 'video', 'game', 'gamer', 'kit', 'combo',
    'pacote', 'oficial', 'padrao', 'standard', 'novo', 'nova', 'jogo',
    'jogos', 'edicao', 'edition', 'pre', 'venda', 'langamento',
    'lancamento', 'importado', 'digital', 'fisico', 'fisica', 'midia',
    'cpu', 'processador', 'amd', 'nucleos', 'nucleo', 'nucleus',
}

# Termos técnicos genéricos que variam entre postagens do mesmo produto
# e não identificam o modelo (plataforma/memória/gui do processador).
_TOKENS_GENERICOS = {
    'ddr3', 'ddr4', 'ddr5', 'am3', 'am4', 'am5', 'lga', 'socket',
    'r3', 'r5', 'r7', 'r9', 'gen', 'series',
    'max', 'turbo', 'box', 'edition', 'retail', 'oem', 'pro', 'plus',
    'mini', 'duo', 'lite', 'slim', 'ultra', 'x', 'maxx',
    'microfone', 'lapela', 'usb', 'c', 'tipo', 'tipo-c', 'versao',
    'original', 'lacrado', 'sem', 'fio', 'wireless', 'usbc',
    'lga', 'lga1851', 'lga1700', 'lga1200', 'lga1151', 'lga2066', 'lga2011',
    '1851', '1700', '1200', '1151', '1150', '2011', '2066', '1366', '775',
    # descritores de celular que não identificam o modelo
    'amoled', 'camara', 'camera', 'super', 'tela', 'polegadas', 'tripla',
    'smartphone', 'galaxy', 'samsung', 'motorola', '4g', '5g', 'fusion',
    'lcd', 'ips', 'hd', 'full', 'nfc', 'oled', 'led', 'mp', 'pixel',
    'ram', 'gb', 'tb', 'rom', 'edge', 'moto',
    'apple', 'iphone', 'ultramarino', 'titanio', 'titanio', 'preto', 'branco',
    '128', '256', '512', '1tb', '2tb', '1000', '1024', '2048',
    # specs de monitor/tela que variam entre anúncios e não identificam o modelo
    'hdr', 'hdr10', 'hdr400', 'hdr600', 'hdr1000', 'freesync', 'gsync',
    'g-sync', 'fhd', 'qhd', 'uhd', 'wqhd', 'freesyncpremium', 'mbr',
}

# Plataformas de console — o JOGO é o mesmo em qualquer uma, então a
# plataforma não deve diferenciar a chave (GTA 6 PS5 = GTA 6 Xbox).
# Obs.: 'ps4'/'ps5'/'ps3' NÃO estão aqui porque são o próprio produto
# quando o anúncio é de console; e 'switch'/'nintendo'/'playstation'/'xbox'
# também, por serem marcas do produto. Só plataformas genéricas de jogo.
_PLATAFORMAS = {
    'series', 'one', 'steam', 'pc', 'pcgamer', 'epic', 'uu', 'redeem',
}

# Marcas genéricas/lojas que podem aparecer no título e não ajudam a
# identificar o produto (não deve remover marcas do produto em si).
_PREFIXOS_LOJA = {
    'aliexpress', 'mercadolivre', 'mercado', 'livre', 'amazon', 'shopee',
    'magalu', 'magazine', 'luiza', 'kabum', 'pichau', 'terabyte',
    'americanas', 'casas', 'bahia', 'walmart', 'fast', 'shop', 'renner',
    'submarino', 'pontofrio', 'ponto', 'cnc', 'seller', 'br',
}

# Marcas de hardware que IDENTIFICAM o produto (ex.: 'Asus B550M' é diferente
# de 'Asrock B550M'). São mantidas na chave do produto para o histórico de
# preços não misturar marcas diferentes que compartilham o mesmo chipset/modelo.
_MARCAS_HARDWARE = {
    'asus', 'asrock', 'gigabyte', 'msi', 'evga', 'galax', 'pny', 'zotac',
    'palit', 'sapphire', 'xfx', 'powercolor', 'aorus', 'biostar', 'colorful',
    'nvidia', 'geforce', 'amd', 'radeon', 'intel', 'xeon',
    'corsair', 'kingston', 'crucial', 'kioxia', 'seagate', 'sandisk',
    'adata', 'hiksemi', 'kootion', 'lexar', 'patriot', 'team',
    'logitech', 'razer', 'redragon', 'hyperx', 'havit', 'jbl', 'edifier',
    'deepcool', 'cooler master', 'noctua', 'lian li', 'nzxt', 'fractal',
    'cougar', 'pcyes', 'gamemax', 'liketec', 'nakasaki', 'makita', 'dewalt',
    'bosch', 'schneider', 'nubom', 'wisetech', 'aoc', 'lg', 'samsung',
    'benq', 'dell', 'hp', 'lenovo', 'acer', 'positivo', 'avell', 'gigastone',
}

# Normalização de sinônimos comuns (chave -> termo canônico).
# 'gta 6' e 'grand theft auto vi' viram a mesma base 'gta6'.
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


def _eh_codigo_modelo(w):
    """True se o token parece um código de produto (mistura de letras e
    dígitos, ex.: '75a400m', 'rtx4060', '5700x', 'bcx4601'). Esses códigos
    são estáveis entre postagens do mesmo produto — diferentemente de
    descritores ('uhd', 'mini led', '2026')."""
    if not w or len(w) < 3:
        return False
    # Padrões de modelo: 'a17', 'g17', 'edge70', 'rx580' (letra(s) + 2+ dígitos).
    if re.fullmatch(r'[a-z]{1,3}\d{2,4}', w):
        return True
    # Número puro de 3-4 dígitos: modelo de GPU/CPU (5060, 4060, 580, 5700).
    # Evita anos ('2026', '2025') e capacidades/medidas já filtradas.
    if re.fullmatch(r'\d{3,4}', w):
        if re.fullmatch(r'20[2-9]\d', w):   # '2025', '2026' — é ano, não modelo
            return False
        return True
    if not (re.search(r'\d', w) and re.search(r'[a-z]', w)):
        return False
    # unidades/medidas comuns que NÃO devem ser tratadas como modelo
    if re.fullmatch(r'\d{1,4}k', w):        # 4k, 8k, 1440k
        return False
    if re.fullmatch(r'\d{1,4}p', w):        # 1080p, 720p
        return False
    # megapixels da câmera ('50mp', '108mp') não é modelo de produto
    if re.fullmatch(r'\d{1,4}mp', w):
        return False
    if re.fullmatch(r'\d{2,4}hz', w):       # 144hz
        return False
    if re.fullmatch(r'\d{2,4}w', w):        # 350w
        return False
    if re.fullmatch(r'\d{1,4}gb', w) or re.fullmatch(r'\d{1,4}tb', w):  # 825gb
        return False
    # medidas/specs que variam e não são modelo: '3.6ghz', '4.2gh', '16mb', '144hz', '1ms'
    if re.fullmatch(r'\d+[\.,]?\d*\s*(?:ghz|gh|hz|mhz|mb|mm|cm|mah|w|v|ms)', w):
        return False
    # tipo de memória (gddr7, ddr4, ddr5) não é modelo
    if re.fullmatch(r'(?:g?ddr|g?ddr\d)[0-9]?', w) or re.fullmatch(r'g?ddr\d+', w):
        return False
    if re.fullmatch(r'\d{1,2}x', w):        # 9x (parcelas)
        return False
    # palavras comuns que têm letra+sobraram (ex.: '7.1', 'sem', 'fio', 'rgb')
    if w in ('sem', 'fio', 'rgb', 'com', 'por', 'para', 'uma', 'novo'):
        return False
    return True


def _tamanho_polegadas(texto_norm):
    """Extrai o tamanho em polegadas de TVs/monitores (ex.: '65' em 'smart tv 65',
    '50' em 'tv 50 polegadas', '27' em 'monitor 27'). Retorna '65' ou ''."""
    if not texto_norm:
        return ''
    # 'tv 50 polegadas', 'monitor 27"', '24 pol', '32 polegadas'
    m = re.search(r'\b(\d{2})\s*(?:["\'\u201d]?\s*(?:pol|polegadas?|polegada))\b', texto_norm)
    if m:
        return m.group(1)
    # Tamanho logo após 'tv'/'monitor' sem a palavra polegadas (ex.: 'smart tv 65')
    m2 = re.search(r'\b(?:tv|monitor)\b[^\d]*\b(\d{2})\b', texto_norm)
    if m2:
        return m2.group(1)
    return ''


def _tipo_produto(texto_norm):
    """Identifica o TIPO do produto (console/headset/controle/jogo/...), para o
    histórico não misturar itens diferentes que compartilham o mesmo modelo.
    Ex.: 'PlayStation 5' console ≠ 'Headset PlayStation 5' ≠ 'Controle PS5'."""
    if not texto_norm:
        return ''
    t = texto_norm
    # Acessórios de áudio
    if re.search(r'\b(?:headset|headphone|fone|fones|auricular|earbuds|pulse\s*(?:elite|3d)|tws)\b', t):
        return 'headset'
    if re.search(r'\b(?:controle|controlador|dualsense|gamepad|joystick|joypad)\b', t):
        return 'controle'
    if re.search(r'\b(?:teclado|keyboard)\b', t):
        return 'teclado'
    if re.search(r'\bmouse\s*pad\b|\bmousepad\b', t):
        return 'mousepad'
    if re.search(r'\b(?:mouse|mice)\b', t):
        return 'mouse'
    if re.search(r'\b(?:monitor|ultrawide|display)\b', t):
        return 'monitor'
    if re.search(r'\b(?:ssd|nvme|hdd|m\.2|hard\s*disk)\b', t):
        return 'ssd'
    if re.search(r'\b(?:processador|cpu|ryzen|xeon|intel\s*core)\b', t):
        return 'processador'
    if re.search(r'\b(?:jogo|jogos|game|midia\s*fisica|blu-?ray)\b', t):
        return 'jogo'
    # 'playstation 5' vira 'ps5' pelo alias ANTES desta função; por isso inclui
    # 'ps5'/'ps4' aqui (console). Acessórios (headset/controle/jogo) já
    # retornaram acima.
    if re.search(r'\b(?:console|videogame|playstation|xbox|nintendo|switch|handheld|ps[1-5])\b', t):
        return 'console'
    return ''


def _chave_produto(titulo):
    """Gera uma chave estável por NOME do produto (normalizado), para agrupar
    o mesmo item independente da loja/link.

    Ex.: 'Console Nintendo Switch 2 LCD 256GB Novo' e
         'Nintendo Switch 2 LCD 256GB' → mesma chave.
         'GTA 6 Jogo Grand Theft Auto VI Edição Standard - PS5' e
         'Jogo Grand Theft Auto VI Edição Standard - PS5' → mesma chave.

    Retorna '' se não sobrar nada útil.
    """
    if not titulo:
        return ''
    t = unicodedata.normalize('NFKD', titulo).encode('ascii', 'ignore').decode('ascii')
    t = re.sub(r'[^\w\s.,!?/]', ' ', t).lower()

    # Aplica sinônimos ANTES de tokenizar (ex.: 'grand theft auto vi' -> 'gta6')
    for pat, cano in _ALIASES:
        t = re.sub(pat, cano, t)

    # Junta sufixo de modelo ao número anterior, para distinguir
    # '5060 ti' (rtx5060ti) de '5060' (rtx5060), '4060 super', etc.
    t = re.sub(r'(\b\d{3,4})\s+(ti|super|sup|s|x|ultra)\b', r'\1\2', t)
    # Junta marca/linha ao número de modelo: 'edge 70' -> 'edge70', 'g 17' -> 'g17'
    t = re.sub(r'\b(edge|galaxy|g|moto|redmi|poco|note|s|iphone)\s+(\d{2})\b', r'\1\2', t)

    palavras = t.split()
    limpas = []
    for w in palavras:
        # Remove pontuação colada ('144hz,' -> '144hz', 'hdr10,' -> 'hdr10').
        # Sem isso, as regex de descarte de specs acima falham e tokens como
        # '144hz,'/'hdr10,' viram 'código de modelo', poluindo a chave e
        # fazendo o histórico de preços não agrupar o mesmo produto.
        w = re.sub(r'[.,()!?/]+$', '', w).strip('.,()!?/')
        if not w:
            continue
        if w in _TOKENS_RUIDO:
            continue
        if w in _TOKENS_TIPO:
            continue
        if w in _TOKENS_GENERICOS:
            continue
        if w in _PLATAFORMAS:
            continue
        if w in _PREFIXOS_LOJA:
            continue
        # características técnicas que variam entre postagens e não mudam o
        # produto: potência '350w', '650w'; 'bluetooth'; taxas '144hz'; etc.
        if re.fullmatch(r'\d{2,4}w', w):
            continue
        if re.fullmatch(r'\d{2,4}hz', w):
            continue
        # Medidas/specs que variam entre postagens do mesmo produto e não
        # identificam o produto: '3.6ghz', '4.2gh', '16mb', '144hz', etc.
        # IMPORTANTE: não remover o modelo real (ex.: '5700x', '5500').
        if re.fullmatch(r'\d+[\.,]?\d*\s*(?:ghz|gh|hz|mhz|mb|gb|tb|w|mm|cm|v|mah|ms)', w):
            continue
        if re.fullmatch(r'\d{1,2}x', w):
            continue  # parcelas ('9x', '12x') — não confundir com modelo '5700x'
        if re.fullmatch(r'\d{2,4}gb', w) or re.fullmatch(r'\d{2,4}tb', w):
            continue  # capacidade de armazenamento varia ('825gb', '1tb')
        if re.fullmatch(r'\d{1,4}mp', w):
            continue  # megapixels da câmera ('50mp', '108mp') não identifica o produto
        if re.fullmatch(r'\d{1,2}', w) or w in ('1000',):
            continue  # números soltos pequenos ('1', '5', '9') não identificam
        # Tamanhos de radiador de water cooler (120/240/360mm) — variam entre
        # postagens e não identificam a marca/modelo. Sem isso, '360' virava
        # 'código de modelo' e o histórico agrupava water coolers de marcas
        # diferentes (ex.: Gigabyte GME 360 com Corsair H150i e Cooler Master).
        if w in ('120', '240', '360'):
            continue
        if w in ('bluetooth', 'wireless', 'sem', 'fio', 'rgb'):
            continue
        if re.fullmatch(r'\(\d+\)', w):
            continue  # '(PRÉ-VENDA)' já vira 'pre venda' -> removido acima
        # remove pontuação isolada
        if not re.search(r'\w', w):
            continue
        limpas.append(w)
    # Remove tokens duplicados preservando a ordem (ex.: 'gta6 gta6' -> 'gta6'),
    # que surgem quando sinônimos se sobrepõem ('GTA 6' + 'Grand Theft Auto VI').
    vistos = set()
    unicos = []
    for w in limpas:
        if w not in vistos:
            vistos.add(w)
            unicos.append(w)

    # Prioriza o CÓDIGO DO MODELO como identificador estável. Tokens descritivos
    # ('uhd', 'mini led', 'google', '2026', '4k', 'qd') variam entre postagens do
    # mesmo produto; já o código (ex.: '75a400m', 'rtx4060', '5700x') não varia,
    # e é isso que faz o histórico agrupar TVs/placas/processadores de lojas e
    # textos diferentes. Se houver código de modelo, ele sozinho é a chave.
    modelos = [w for w in unicos if _eh_codigo_modelo(w)]
    # Tamanho (polegadas) de TV/monitor — separa tamanhos diferentes do mesmo
    # modelo (ex.: M75H 50" vs 65", monitor 24" vs 27").
    tamanho = _tamanho_polegadas(t)
    # Tipo do produto — separa 'PlayStation 5' (console) de 'Headset PS5' /
    # 'Controle PS5' / 'Jogo PS5' que compartilham o modelo 'ps5'.
    tipo = _tipo_produto(t)

    def _dedup(seq):
        vistos = set()
        out = []
        for w in seq:
            if w not in vistos:
                vistos.add(w)
                out.append(w)
        return out

    if modelos:
        # Inclui a MARCA na chave: 'Asus B550M' ≠ 'Asrock B550M' (mesmo
        # chipset, marcas diferentes). Sem isso, o histórico mistura placas
        # de marcas diferentes que compartilham o modelo.
        marcas = [w for w in unicos if w in _MARCAS_HARDWARE]
        chave = ' '.join(_dedup(
            ([tipo] if tipo else []) + marcas + ([tamanho] if tamanho else []) + modelos
        ))
    else:
        # Ordena os tokens para que a ordem das palavras não importe
        # ('mouse redragon invader' = 'redragon invader mouse').
        base = _dedup(([tipo] if tipo else []) + ([tamanho] if tamanho else []) + unicos)
        chave = ' '.join(sorted(base))
    chave = re.sub(r'\s+', ' ', chave).strip()
    return chave


def _preco_do_texto(texto):
    """
    Extrai o preço real do produto, normalizado.

    Prioriza preços rotulados ('Valor:', 'Preço:', 'Por:', 'R$ no link')
    e ignora valores de CUPOM (ex.: 'cupom de R$90 OFF', 'R$90 de desconto'),
    evitando mostrar o desconto como se fosse o preço do produto.
    """
    texto = texto or ''
    linhas = texto.split('\n')

    # 1) Preço rotulado explicitamente (pulando linhas de cupom/desconto)
    for linha in linhas:
        baixa = linha.casefold()
        if any(palavra in baixa for palavra in ('cupom', 'off', 'desconto', 'economize')):
            continue
        if any(rotulo in baixa for rotulo in ('valor:', 'preço:', 'preco:', 'por apenas', 'por:', 'preco final')):
            m = re.search(r'R\$\s*[\d.,]+', linha)
            if m:
                return m.group(0).strip()

    # 2) Primeiro R$ que NÃO esteja associado a cupom/desconto
    for linha in linhas:
        baixa = linha.casefold()
        if any(palavra in baixa for palavra in ('cupom', 'off', 'desconto', 'economize', 'use o código', 'use o codigo')):
            continue
        # Pula linhas de nota/bullet ('- O da Shopee cobra R$ 400,00++ de
        # frete') e linhas que citam R$ só como frete/comissão, não o preço.
        if baixa.lstrip().startswith('-'):
            continue
        if any(palavra in baixa for palavra in ('frete', 'comissao', 'cobra', 'de entrega')):
            continue
        # Pula linhas de teaser/parcelamento que mencionam R$ mas não são o
        # preço do produto (ex.: 'caiu quase R$ 400,00!', 'em 9x sem juros').
        if re.search(r'^\s*(?:caiu|quase|baixou|barateou|despencou|deixa|agarra|sobe|limite)\b', baixa):
            continue
        if re.search(r'\b(?:x|vezes)\s*sem\s*juros\b', baixa):
            continue
        m = re.search(r'R\$\s*[\d.,]+', linha)
        if m:
            return m.group(0).strip()

    # 3) Fallback: primeiro R$ do texto inteiro
    m = re.search(r'R\$\s*[\d.,]+', texto)
    if m:
        return m.group(0).strip()
    return ''


def _preco_reais(preco):
    """Converte um preço ('R$ 1.877,98', '877.98', etc.) no valor inteiro de
    REAIS, ignorando os centavos. Retorna int ou None. Usado para comparar
    ofertas: 'R$ 877,00' e 'R$ 877,98' contam como o mesmo valor (877)."""
    if preco is None:
        return None
    s = re.sub(r'[^\d.,]', '', str(preco))
    if not s:
        return None
    if ',' in s:
        # vírgula é o separador decimal (formato BR)
        inteiro = s.split(',')[0]
    elif '.' in s:
        partes = s.split('.')
        # '877.98' -> decimal; '1.877' -> milhar
        inteiro = '.'.join(partes[:-1]) if len(partes[-1]) == 2 else s
    else:
        inteiro = s
    inteiro = inteiro.replace('.', '').replace(',', '')
    try:
        return int(inteiro)
    except Exception:
        return None


# Linhas que devem ser ignoradas ao montar o título do produto
_TERMOS_CABECALHO = [
    'postagem original', 'postagem',
    'canal oficial', 'repostagem', 'repost', 'promo do dia',
    'oferta do dia', 'compra garantida',
    'confira todos os detalhes da oferta', 'confira todos os detalhes',
    'veja todos os detalhes da oferta', 'veja todos os detalhes',
    'todos os detalhes da oferta', 'confira a oferta', 'confira as nossas ofertas',
    'disponivel', 'disponível', 'estoque limitado', 'ultimas unidades',
    'poucas unidades', 'últimas unidades', 'ultima chance', 'última chance',
    'corre que ainda', 'corre que', 'saiu rapidinho', 'está acabando', 'ta acabando',
    'alerta para', 'alerta pra', 'precinho', 'precinho d+', 'aproveite',
    'super precinho', 'imperdivel', 'imperdível', 'olha que', 'olha só',
    'pega essa', 'pega esse', 'pipoca do caos', 'anon esbarrou',
    'voltou', 'voltei', 'de volta', 'de novo', 'aconteceu denovo',
    'ativou para quem', 'ativou ontem', 'para quem resgatou', 'quem resgatou',
    'resgatou ontem', 'resgataram ontem', 'quem pegou ontem', 'pegou ontem',
    'parcelado', 'parcelado em', 'em até', 'sem juros', 'com cupom',
    'para primeira compra', 'primeira compra na', 'conta prime',
    'para primeira', 'na amazon e conta', 'na shopee e conta',
    'use o cupom', 'usar o cupom', 'aplique o cupom',
    'valido em selecionados', 'válido em selecionados', 'selecionados na lista',
    'promocao pode encerrar', 'promoção pode encerrar', 'pode encerrar a qualquer momento',
    'encerrar a qualquer momento', 'a promoção pode encerrar', 'a promocao pode encerrar',
    'imagem da postagem', 'imagem da publicação', 'imagens da postagem',
    'compartilhar', 'compartilhe',
]
_LOJAS = [
    'aliexpress', 'mercadolivre', 'mercado livre', 'amazon', 'shopee',
    'magalu', 'magazine luiza', 'kabum', 'pichau', 'terabyte', 'americanas',
    'casas bahia', 'extra', 'wish', 'walmart', 'fast shop', 'pontofrio',
    'cnc', 'saraiva', 'submarino', 'lojas rener', 'renner', 'nike', 'adidas',
    'amaro', 'petlove', 'meli', 'farma', 'daki',
]


# Palavras-termo de instruções/cupom. Testadas como PALAVRA INTEIRA
# (ex.: 'use' não deve bater com 'mouse'). Várias palavras -> aceitas
# em qualquer parte da linha.
_TERMOS_CUPOM_INSTRUCAO = [
    'cupom', 'resgate', 'link', 'carrinho', 'siga', 'use', 'ativa',
    'moedas', 'no app', 'r$', 'desconto', 'off', 'economize', 'valido',
    'válido', 'clique', 'aproveite', 'pega o cupom',
]


def _eh_linha_cupom_instrucao(baixa):
    """True se a linha tem uma palavra de instrução de cupom (por palavra inteira)."""
    for termo in _TERMOS_CUPOM_INSTRUCAO:
        if re.search(r'(?<!\w)' + re.escape(termo) + r'(?!\w)', baixa):
            return True
    return False


# Cores comuns que aparecem no início do título (ex.: '(PRETO) ', 'PRETO ').
# Removidas do título, pois não identificam o produto.
_CORES_TITULO = {
    'preto', 'preta', 'black', 'branco', 'branca', 'white', 'vermelho',
    'vermelha', 'red', 'azul', 'blue', 'verde', 'green', 'amarelo', 'amarela',
    'yellow', 'cinza', 'cinza', 'grey', 'gray', 'roxo', 'roxa', 'lilás',
    'lilas', 'marrom', 'rose', 'rosa', 'pink', 'dourado', 'dourada', 'dourado',
    'prata', 'prateado', 'prateada', 'silver', 'bege', 'beige',
}


# Chamadas de engajamento do canal (teasers) que vêm ANTES do produto.
# Ex.: 'Cade Os Chefs Do Grupo ??' — ignoradas na escolha do título.
_TERMOS_TEASER = [
    'cade os', 'cade o', 'cadê os', 'cadê o', 'cade',
    'quem quer', 'quem quer ver', 'quem procura', 'quem ta', 'quem tá',
    'reage', 'reagiu', 'topa?', 'quer ver?', 'bora', 'vamo', 'vamos',
    'olha isso', 'olha so', 'olha só', 'muito bom', 'sim ou nao',
    'alquem ta', 'tem alguem', 'alguem conseguiu', 'quem vai',
    'pera ai', 'espera ai', 'cade o pessoal', 'cade voces',
    'ainda no preço', 'ainda no preco', 'ainda no precinho', 'ainda no preção',
    'no precinho', 'preço antigo', 'preco antigo', 'veio o preço', 'veio o preco',
    'segura esse', 'segura essa', 'conseguiram', 'depois dessa', 'se liga',
]


def _eh_linha_nota(baixa):
    """True se a linha é uma nota/teaser do canal (ex.: 'dica do brendo3d',
    'cade os chefs do grupo'), não um título de produto/cupom."""
    if bool(re.search(r'(?<!\w)dica(?!\w)', baixa)):
        return True
    if any(nota in baixa for nota in ('obs:', 'nota:', 'atencao:', 'atenção:')):
        return True
    # Linha que é só um cabeçalho de garantia ('compra garantida',
    # 'nota fiscal', 'enviamos para todo brasil') — descarta se a linha é só
    # isso ou começa com o termo; mas NÃO descarta quando 'nota fiscal' é só
    # parte do título do produto ('iPhone ... com Nota Fiscal').
    if re.match(r'^\s*(?:compra\s+garantida|nota\s+fiscal|enviamos\s+para\s+todo\s+brasil|produto\s+no\s+brasil|produto\s+original)\b.*$', baixa):
        return True
    # Teasers de PREÇO ('caiu quase r$ 400,00!', 'caiu de r$ 500 pra 399',
    # 'baixou pra', 'barateou', 'quase r$ x') — não são o nome do produto.
    if re.search(r'^\s*(?:caiu|quase|caiu\s+(?:quase|pra|para)|baixou|barateou|despencou|agarra|pega)\b.*r\s?[0-9]', baixa):
        return True
    # Rótulo de preço (ex.: 'Valor R$ 4.837,09', 'Preço: R$ 999,00') — não é
    # o nome do produto; o título real vem logo depois.
    if re.match(r'^\s*(?:valor|preco|preço)\b[^a-z]{0,3}(?:r\s?[\$\$]?)?\b', baixa) and \
       re.search(r'[\d.,]+', baixa):
        return True
    if re.match(r'^\s*(?:valor|preco|preço)\s*[:]?\s*r\s?[\$\$]\s*[\d.,]+', baixa):
        return True
    if re.search(r'^\s*caiu\b', baixa) and len(baixa) < 40:
        return True
    # Chamadas de engajamento do canal (teasers) que vêm antes do produto.
    # Confere no INÍCIO da linha, com palavra inteira ('cade' não bate com
    # 'cadeira').
    for frase in _TERMOS_TEASER:
        if re.search(r'^(?:\w+\s+)*' + re.escape(frase) + r'(?!\w)', baixa):
            return True
    # Perguntas de engajamento do canal (ex.: 'VEGETTO ou GOGETA CHAT?',
    # 'quem e melhor?') — terminam com 'chat?' ou são interrogações do canal.
    if baixa.rstrip(' ').endswith('chat?'):
        return True
    if re.search(r'\b(diga|fala|responde|comenta|cade|cadê)\b.*\?$', baixa):
        return True
    return False


def _eh_linha_quantidade(baixa):
    """True se a linha indica apenas a quantidade de itens/estoque da oferta
    (ex.: '2 Peças!', 'Kit 2 peças', '1 Peça', '1 Pç no estoque'),
    não o nome do produto. Essas linhas costumam vir antes do título real."""
    if not baixa:
        return False
    # 'N peça/peças/pç/un/unidade/item/itens' (+ opcional 'no estoque'/'estoque')
    if re.search(r'^\d{1,3}\s+(?:(?:peca|peça|pecas|peças|p[cç]s?|un|unidade|unidades|item|itens)(?:s)?)[!.]?\s*(?:no\s+estoque|estoque|dispon[íi]veis?|restantes?)?[!.]?$', baixa):
        return True
    # 'ÚLTIMAS 7 UNIDADES' / 'ÚLTIMAS 3 PEÇAS' — aviso de estoque, não é o produto.
    if re.search(r'^(?:ultimas|últimas)\s+\d{1,3}\s+(?:(?:peca|peça|pecas|peças|p[cç]s?|un|unidade|unidades|item|itens)(?:s)?)[!.]?$', baixa):
        return True
    if re.search(r'^kit\s+\d{1,3}\s+(?:(?:peca|peça|pecas|peças|p[cç]s?|un|unidade|unidades|item|itens)(?:s)?)[!.]?\s*(?:no\s+estoque|estoque)?[!.]?$', baixa):
        return True
    # 'X no estoque' / 'X unidades restantes' (só número + estoque)
    if re.search(r'^\d{1,3}\s+(?:em\s+)?(?:no\s+)?estoque\s*(?:tem|sobrou|resta)?[!.]?$', baixa):
        return True
    return False


def _eh_anuncio_cupom(limpa):
    """True se a linha é um anúncio curto de cupom (ex.: 'Novo Cupom AMAZON',
    'CUPONS ATIVOS SHOPEE - Resgate no link'),
    distinto de uma instrução de cupom QUE NÃO começa por cupom
    (ex.: 'use o cupom X')."""
    baixa = limpa.casefold()
    if not re.search(r'\b(?:cupom|cupons|cupoms)\b', baixa):
        return False
    if len(limpa) > 60:
        return False
    # Se começa com 'cupom(s)', é um ANÚNCIO de cupom — mesmo que tenha
    # uma instrução de resgate depois (ex.: 'CUPONS ATIVOS SHOPEE - Resgate...').
    if re.match(r'^\s*(?:novo|novos|nova|novos)?\s*(?:cupom|cupons|cupoms)\b', baixa):
        return True
    for termo in ('use ', 'usem', 'usem o', 'usar', 'usar o', 'usa ', 'usa o',
                  'siga', 'resgate', 'clique', 'pega', 'atraves',
                  'no app', 'válido', 'valido', 'ativar'):
        if re.search(r'(?<!\w)' + re.escape(termo) + r'(?!\w)', baixa):
            return False
    return True


# Termos fortes que indicam que a linha é o nome de um produto real
# (não um código de cupom, rótulo de loja ou instrução).
_TERMOS_PRODUTO = [
    'water cooler', 'watercooler', 'cooler', 'ssd', 'nvme', 'placa de video',
    'processador', 'ryzen', 'monitor', 'notebook', 'headset', 'fone', 'teclado',
    'mouse', 'gabinete', 'fonte', 'memoria', 'ram', 'placa mae', 'caixa de som', 'caixas de som',
    'soundbar', 'microfone', 'webcam', 'controle', 'controlador', 'gamepad',
    'joystick', 'joypad', 'dualsense', 'jogo', 'gta', 'tv', 'celular',
    'smartphone',     'cadeira', 'mesa', 'impressora', 'roteador', 'console', 'console',
    'pc gamer', 'computador gamer',
    'pasta termica', 'pasta térmica', 'gpu', 'videogame', 'fans', 'fan',
    'ventoinha', 'ventoinhas', 'air fryer', 'batedeira', 'liquidificador', 'secador', 'aspirador',
    'chaleira', 'panela', 'panelas', 'fogao', 'fogão', 'cafeteira', 'torradeira',
    'sanduicheira', 'pipoqueira', 'frigideira', 'grill', 'jarra', 'garrafa termica',
    'garrafa térmica', 'termo', 'microondas', 'micro-ondas', 'forno', 'geladeira',
    'frigobar', 'lavadora', 'coifa', 'multiprocessador', 'espremedor', 'talher', 'talheres',
    'jogo de copos', 'utensilios', 'utensílios', 'porta temperos', 'faqueiro',
    'filtro', 'regua', 'tomadas', 'tomada', 'extensao', 'extensão',
    'carregador', 'carregadores', 'carregamento', 'power bank', 'powerbank',
    'iphone', 'xiaomi', 'redmi', 'poco', 'realme', 'samsung', 'galaxy', 'motorola',
    'tablet', 'ipad', 'ar condicionado', 'condicionador', 'smart tv', 'qled', 'oled',
    'starlink', 'soprador',
    'cambio', 'câmbio', 'shifter', 'logitech', 'driving force', 'sim racing',
    'volante', 'pedaleira', 'racing wheel', 'simulator', 'simulador',
    'parafusadeira', 'motosserra', 'furadeira', 'esmerilhadeira', 'lixadeira',
    'serra', 'tupia', 'nakasaki', 'makita', 'dewalt', 'bosch', 'skil',
    'ferramenta', 'ferramentas', 'broca', 'chave de fenda', 'chave de impacto',
    'soprador', 'roçadeira', 'roçadeira', 'grampeador', 'pistola', 'maquita',
    'camera', 'câmera', 'cameras', 'câmeras', 'seguranca', 'segurança', 'cftv',
    'icsee', 'ip camera', 'video monitoramento', 'monitoramento', 'dvr', 'nvr',
]


def _eh_linha_titulo_produto(linha):
    """True se a linha normalizada parece ser o nome de um produto real.

    Usado para decidir se uma mensagem com 'Cupom: X' é um PRODUTO com
    cupom (ex.: 'Water Cooler ... cupom GAMER10') ou um anúncio só de cupom.
    """
    if not linha:
        return False
    # Código de cupom: linha sem espaço (ex.: '99TOPHIGH') não é produto.
    if ' ' not in linha.strip():
        return False
    linha_c = linha.strip()
    # Anúncio de cupom (ex.: 'novo cupom kabum', 'cupom ativo shopee') e
    # linhas de instrução de cupom ('resgate o cupom de 20%') NÃO são produto.
    if re.match(r'^(?:novo|novos|nova)\s+cupom\b', linha_c) or re.match(r'^cupom\b', linha_c):
        return False
    # Linha que começa pela instrução de resgate/uso de cupom (ex.: 'resgate o
    # cupom de 20%') é anúncio de cupom. Mas se a linha traz um produto ANTES
    # ('iPhone 17 ... Resgate o cupom de R$220'), é produto com cupom.
    if re.match(r'^(?:resgate|use|usar|aplicar|aproveite|clique|siga)\b', linha_c) and \
       re.search(r'\bcupom\b', linha_c):
        return False
    tem_termo = any(t in linha for t in _TERMOS_PRODUTO)
    tem_cupom = re.search(r'\bcupoms?\b', linha)
    # Linha com 'cupom' e sem termo de produto → anúncio de cupom, não produto.
    if tem_cupom and not tem_termo:
        return False
    if tem_termo:
        return True
    # Linha só de desconto ('R$ 150,00 OFF a partir de R$ 999,00: 3SQUENT4150')
    # sem termo de produto: o token com letra+dígito é o CÓDIGO do cupom, não
    # um modelo de produto — senão a heurística de 'modelo' faria a postagem
    # de cupom parecer produto e a categoria não seria 'cupom'.
    if re.search(r'\b(?:off|desconto|descontos)\b', linha):
        return False
    # Nome de produto sem termos conhecidos: tem >= 2 palavras e uma delas
    # parece modelo (mistura letra+digito), ex.: 'gk240', 'k688'.
    palavras = [w for w in linha.split() if re.search(r'\w', w)]
    if len(palavras) >= 2:
        for w in palavras:
            if re.search(r'\d', w) and re.search(r'[a-z]', w) and len(w) >= 3:
                return True
    return False


def _limpar_cor_inicio(texto):
    """Remove uma cor que apareça no INÍCIO do título (ex.: 'PRETO Mousepad',
    '(preto) Mousepad'), já que cor não identifica o produto."""
    if not texto:
        return texto
    limpo = texto.strip()
    primeira = re.split(r'\s+', limpo)[0].strip('()[]{}_-,.')
    if primeira.casefold() in _CORES_TITULO:
        return re.sub(r'^[\s\w-]+?\s+', '', limpo, count=1)
    return limpo


def _linha_titulo(texto):
    """
    Pega a primeira linha que parece título (de produto ou de cupom),
    ignorando cabeçalhos ('Postagem original'), nomes de loja e
    instruções que costumam vir ANTES do título real.

    Percorre as linhas em ORDEM e aceita como título:
      - uma linha curta de anúncio de cupom (ex.: 'Novo Cupom AMAZON');
      - ou uma linha que pareça nome de produto;
    exceto quando é header/loja/código/instrução.
    """
    texto = texto or ''
    tem_cupom = 'cupom' in texto.casefold() or 'cupons' in texto.casefold()
    cupom_candidata = None

    for linha in texto.split('\n'):
        limpa = re.sub(r'[^\w\s.,!?-]', '', linha).strip()
        baixa = limpa.casefold()
        if not limpa or len(limpa) <= 5:
            continue
        if not re.search(r'\s', limpa):
            continue  # código de cupom sem espaços (ex: S3M4N488)
        if limpa.lstrip().startswith('-'):
            continue  # nota/bullet (ex.: '-Direto do Brasil')
        if _eh_linha_nota(baixa):
            continue  # nota do canal (ex.: 'dica do brendo3d')
        if _eh_linha_quantidade(baixa):
            continue  # quantidade de itens (ex.: '2 Peças!') — não é o produto
        # Data/hora (ex.: '11/09 às 07:58', 'hoje 09:00') não é título de produto.
        # Mas modelos de produto (ex.: 'iPhone 15/16', 'Galaxy S24/25') NÃO são datas.
        _eh_produto_modelo = re.search(
            r'\b(?:iphone|ipad|galaxy|celular|phone|samsung|xiaomi|realme|poco|motorola|'
            r'notebook|monitor|mouse|teclado|headset|fone|gpu|rtx|ssd|placa)\b', baixa
        )
        if not _eh_produto_modelo and (
            re.search(r'\b\d{1,2}[/:][0-9]{1,2}\b', linha) or
            (re.search(r'\b(?:\d{1,2}\s+de\s+[a-záéíóúç]+|\d{1,2}/\d{1,2}/\d{2,4})\b', baixa) and
             not re.search(r'\b(?:rtx|gpu|placa|rtx\s?\d|monitor|notebook|ssd)\b', baixa))
        ):
            continue
        if any(prefixo in baixa for prefixo in _TERMOS_CABECALHO):
            continue
        if tem_cupom and _eh_anuncio_cupom(limpa):
            # Rótulo/linha de anúncio de cupom (ex.: 'Cupom', 'Novo Cupom
            # AMAZON'). Guarda como candidata, mas se houver um PRODUTO real
            # mais abaixo ('RTX 5070 Ti Placa de Video...'), o título do card
            # deve ser o produto — não a linha 'Cupom'.
            if cupom_candidata is None:
                cupom_candidata = limpa
            continue
        if tem_cupom and _eh_linha_cupom_instrucao(baixa):
            continue
        if any(loja in baixa for loja in _LOJAS) and len(limpa) < 30:
            continue
        return _limpar_cor_inicio(limpa)

    if cupom_candidata is not None:
        return cupom_candidata

    # Fallback: texto curto é só uma instrução/cupom ('Resgate o cupom de
    # R$200 OFF') e não há outra linha — usa a própria linha, pra não deixar
    # o card sem título.
    for linha in texto.split('\n'):
        limpa = re.sub(r'[^\w\s.,!?%-]', '', linha).strip()
        baixa_fb = limpa.casefold()
        if len(limpa) <= 6 or not re.search(r'\s', limpa):
            continue
        if any(loja in baixa_fb for loja in _LOJAS) and len(limpa) < 30:
            continue
        if any(p in baixa_fb for p in _TERMOS_CABECALHO):
            continue
        if _eh_linha_nota(baixa_fb):
            continue
        return limpa
    return ''


def _linha_marcador_link(linha):
    """True se a linha é um rótulo/marcador de link (ex.: '⬇️',
    '⬇️ NO PC', '🥇 Link com moedas:', '🖥 Link para PC:', '🔗 Link').
    Essas linhas precedem as URLs e não devem aparecer no card."""
    if not linha:
        return True
    baixa = linha.casefold().strip()
    # setas / cadeado / labels claros de link
    if any(s in linha for s in ('⬇', '🔗', '🖥', '🥇', '↓', 'glyph', 'chainem')):
        return True
    if re.search(r'\b(link|pcinho|removido done)\b', baixa) and len(linha) < 40:
        # Só trata como rótulo se a linha for um rótulo curto de verdade:
        # começa com 'link' (ex.: 'Link com moedas') ou termina em ':' (ex.: 'Link:').
        # Evita cortar em linhas que apenas mencionam 'link' (ex.: '3 Modelos no link').
        if re.match(r'^[^\w]*\blink\b', baixa) or baixa.rstrip().endswith(':'):
            return True
    if re.search(r'\bno pc\b|\bpara pc\b|\bcom moedas\b|\bcommoedas\b', baixa) and len(linha) < 40:
        return True
    return False


def texto_card(texto):
    """Copia fiel do texto do Telegram para o card do site.

    Mantém tudo exatamente como postado (cabeçalho tipo '🇧🇷 Aliexpress',
    'Produto no Brasil', '12x sem juros', emojis, valor, cupom), removendo
    apenas o marcador fixo 'Postagem original' e toda a seção de links
    (URLs + marcadores tipo '⬇️', '🥇 Link com moedas:'). Retorna a
    mensagem multi-linha completa."""
    if not texto:
        return ''
    linhas = []
    for linha in texto.split('\n'):
        limpa = linha.strip()
        if not limpa:
            if linhas:
                linhas.append('')
            continue
        baixa = limpa.casefold()
        # marca o fim: primeira URL ou marcador de link -> para aqui
        if re.search(r'(?i)\bhttps?://\S+', limpa):
            break
        if _linha_marcador_link(limpa):
            break
        if baixa in ('postagem original', 'postagem original ',
                     'postagem', 'a postagem'):
            continue
        linhas.append(limpa)
    return '\n'.join(linhas).strip()


def _chave_dedup(texto):
    """
    Chave de deduplicação estável: link do produto + preço.
    Assim, a MESMA página de produto com preço/cupom diferente
    é tratada como uma NOVA oferta (não é ignorada).
    """
    link = _normalizar_url(_primeiro_link_produto(texto))
    preco = _preco_do_texto(texto)
    if link:
        return f"{link}|{preco}"
    return link


def promo_ja_postada(texto):
    """
    Verifica se uma promoção já foi postada/salva antes.
    Usa uma chave normalizada do PRIMEIRO LINK BRUTO da mensagem,
    que é estável entre restarts (diferente do link convertido/short).
    Retorna True se já existe (deve pular o envio).
    """
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import Promo

    chave = _chave_dedup(texto)
    if not chave:
        return False

    try:
        return Promo.objects.filter(url_chave=chave).exists()
    except Exception as db_err:
        print(f"Erro ao verificar promo existente: {db_err}")
        return False


def promo_repetida_recente(texto, janela_minutos=1440):
    """
    Verifica se uma promoção IGUAL já foi capturada recentemente dentro da
    janela (padrão 24h). Considera IGUAL quando bate o link OU o título, e o
    PREÇO em REAIS (ignorando centavos): 'R$ 877,00' e 'R$ 877,98' contam como
    o mesmo valor; 'R$ 877' e 'R$ 878' contam como diferentes.
    Evita spam quando o canal da fonte publica a MESMA oferta repetida.

    Retorna True se já existir uma promo igual criada dentro da janela
    (deve ignorar a oferta).
    """
    from django.db import close_old_connections
    from datetime import timedelta
    from django.utils import timezone
    close_old_connections()
    from bot.models import Promo

    limite = timezone.now() - timedelta(minutes=janela_minutos)
    try:
        link = _normalizar_url(_primeiro_link_produto(texto))
        preco_int = _preco_reais(_preco_do_texto(texto))

        # 1) Mesmo link (preço comparado em reais inteiros)
        if link:
            chaves = Promo.objects.filter(
                url_chave__startswith=link + '|', criado_em__gte=limite
            ).values_list('url_chave', flat=True)
            for uc in chaves:
                p = uc.split('|', 1)[1] if '|' in uc else ''
                if _preco_reais(p) == preco_int:
                    return True

        # 2) Mesmo título (link pode ter mudado; preço em reais inteiros)
        try:
            titulo = _linha_titulo(texto)[:500]
        except Exception:
            titulo = ''
        if titulo:
            precos = Promo.objects.filter(
                titulo=titulo, criado_em__gte=limite
            ).values_list('preco', flat=True)
            for p in precos:
                if _preco_reais(p) == preco_int:
                    return True

        # 3) Mesmo produto (produto_chave normalizado) + mesmo preço.
        # Cobre variações de emoji/acento/formato no título que a regra 2
        # pode deixar passar (ex.: mesma oferta repostada com emoji diferente).
        try:
            pchave = _chave_produto(titulo) if titulo else ''
        except Exception:
            pchave = ''
        if pchave:
            precos2 = Promo.objects.filter(
                produto_chave=pchave, criado_em__gte=limite
            ).values_list('preco', flat=True)
            for p in precos2:
                if _preco_reais(p) == preco_int:
                    return True
        return False
    except Exception as db_err:
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️ Erro ao verificar promo repetida recente: {db_err}")
        return False


def _converter_para_webp(origem, destino_dir, prefixo='promo', max_lado=900, qualidade=82):
    """Converte a imagem 'origem' para WebP (redimensionada para max_lado) e
    salva em destino_dir com nome '<prefixo>_<timestamp>_<nome>.webp'.

    Retorna (filename, caminho_absoluto) ou (None, None) se falhar.
    """
    from PIL import Image, ImageOps
    import re as _re
    nome = os.path.basename(origem)
    base = _re.sub(r'[^A-Za-z0-9_.-]', '_', os.path.splitext(nome)[0])[:80] or 'img'
    filename = f'{prefixo}_{int(time.time())}_{base}.webp'
    out_path = os.path.join(destino_dir, filename)
    try:
        with Image.open(origem) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode in ('RGBA', 'LA', 'P'):
                if img.mode == 'P':
                    img = img.convert('RGBA')
                fundo = Image.new('RGB', img.size, (255, 255, 255))
                fundo.paste(img, mask=img.split()[-1])
                img = fundo
            else:
                img = img.convert('RGB')
            if max(img.size) > max_lado:
                img.thumbnail((max_lado, max_lado), Image.LANCZOS)
            img.save(out_path, 'WEBP', quality=qualidade, method=4, optimize=True)
        return filename, out_path
    except Exception:
        return None, None


def save_promo_to_db(texto, photo_path=None, fonte='zFinnY', url_chave=None):
    """
    Salva a promoção no banco de dados para exibição na página web.
    Réplica fiel do texto enviado ao Telegram.
    photo_path pode ser um caminho local ou uma URL de imagem.
    url_chave: chave normalizada do link bruto original (para deduplicação estável).
    """
    from django.db import close_old_connections
    close_old_connections()
    from bot.models import Promo

    if not url_chave:
        url_chave = _chave_dedup(texto)

    # Deduplicação por url_chave: DESATIVADO a pedido do usuário.
    # Todas as promoções são salvas, sem ignorar por "já postada".
    # if url_chave:
    #     ja_existe = Promo.objects.filter(url_chave=url_chave).exists()
    #     if ja_existe:
    #         print(f"Promo já existente, ignorada: {url_chave}")
    #         return False

    # Extrai título (linha do produto) e o usa como pista da categoria
    titulo = _linha_titulo(texto)[:250]

    # Detecta categoria pelo texto/título
    from bot.classifier import detectar_categoria
    categoria = detectar_categoria(texto, titulo=titulo)

    # Link do produto (para o botão de compra) — prioriza o link marcado como
    # 'Link do produto' em vez do link do cupom, quando ambos aparecem.
    link_afiliado = _link_produto_compra(texto)

    # Loja detectada pelo domínio do link de compra
    from bot.classifier import detectar_loja
    loja = detectar_loja(link_afiliado)

    # Preço básico para filtro
    preco = _preco_do_texto(texto)

    # Processa imagem. Sempre usa a foto original da postagem (não há mais
    # substituição por imagem fixa de cupom do Mercado Livre).
    imagem_url = ''
    media_promos_dir = os.path.join(settings.MEDIA_ROOT, 'promos')

    def _salvar_imagem_site(origem, prefixo):
        """Salva a imagem no site: converte para WebP (leve, sem "tremida" na
        rolagem). Se a conversão falhar, copia o arquivo original."""
        os.makedirs(media_promos_dir, exist_ok=True)
        convertida, _path = _converter_para_webp(origem, media_promos_dir, prefixo=prefixo)
        if convertida:
            return convertida
        import shutil
        filename = f"{prefixo}_{int(time.time())}_{os.path.basename(origem)}"
        shutil.copy2(origem, os.path.join(media_promos_dir, filename))
        return filename

    if not imagem_url and photo_path:
        try:
            if isinstance(photo_path, str) and photo_path.startswith('http'):
                # URL externa (ex.: imagem do produto Shopee): baixa e converte
                # para não deixar uma imagem pesada/hotlinked no site.
                import tempfile
                import urllib.request
                req = urllib.request.Request(photo_path, headers={'User-Agent': 'Mozilla/5.0 (NitroTech)'})
                tmp_img = os.path.join(tempfile.gettempdir(), f"promo_dl_{int(time.time())}.img")
                with urllib.request.urlopen(req, timeout=20) as resp, open(tmp_img, 'wb') as f:
                    f.write(resp.read())
                if os.path.getsize(tmp_img) < 1024:
                    raise ValueError('download de imagem inválido (muito pequeno)')
                try:
                    filename = _salvar_imagem_site(tmp_img, 'promo')
                    imagem_url = f"{settings.MEDIA_URL}promos/{filename}"
                finally:
                    if os.path.exists(tmp_img):
                        os.remove(tmp_img)
            elif os.path.exists(photo_path):
                filename = _salvar_imagem_site(photo_path, 'promo')
                imagem_url = f"{settings.MEDIA_URL}promos/{filename}"
        except Exception as img_err:
            print(f"Erro imagem: {img_err}")
            if isinstance(photo_path, str) and photo_path.startswith('http'):
                imagem_url = photo_path  # fallback: mantém o link original

    # Deduplicação por link_afiliado: DESATIVADO a pedido do usuário.
    # Todas as promoções são salvas, sem ignorar por "já postada".
    # if link_afiliado:
    #     ja_existe = Promo.objects.filter(link_afiliado=link_afiliado).exists()
    #     if ja_existe:
    #         ja_existe_mesmo_preco = Promo.objects.filter(
    #             link_afiliado=link_afiliado,
    #             preco=preco,
    #         ).exists()
    #         if not ja_existe_mesmo_preco:
    #             print(f"Promo já salva antes, mas com preço diferente ({preco}): tratando como nova oferta.")
    #         else:
    #             print(f"Promo já existente, ignorada: {link_afiliado[:80]}")
    #             return False

    # Chave do produto: nome normalizado (identifica o mesmo produto em
    # qualquer loja/link, mesmo que o preço mude ou a postagem seja repetida).
    produto_chave = _chave_produto(titulo)

    # Salva
    try:
        promo = Promo.objects.create(
            titulo=titulo or "Oferta imperdível",
            preco=preco,
            cupom='',
            link_afiliado=link_afiliado,
            url_chave=url_chave,
            produto_chave=produto_chave,
            imagem_url=imagem_url,
            categoria=categoria,
            loja=loja,
            fonte=fonte,
            texto_original=texto
        )
        print(f"Promo salva: {titulo[:30]} (id={promo.id})")
        return promo.id
    except Exception as db_err:
        print(f"Erro DB: {db_err}")
        return False


def get_product_info(url):
    """
    Extrai informações do produto da URL e da página (Shopee ou AliExpress).
    """
    name = None
    image_url = None
    price = None

    try:
        # ── Nome via Slug (Shopee) ────────────────────────────────────────
        if 'shopee' in url:
            slug_match = re.search(r'shopee\.com\.br/([^/?]+?)(?:-i\.\d+\.\d+)', url)
            if slug_match:
                slug = slug_match.group(1)
                name = slug.replace('-', ' ').title()

        # ── Scraping Geral (Meta tags e Preço) ────────────────────────────
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        
        # Injeta Cookies se for Mercado Livre
        if 'mercadolivre.com' in url or 'mercadolibre.com' in url:
            ml_cookie = getattr(settings, 'MERCADO_LIVRE_COOKIE', None)
            if ml_cookie:
                headers["Cookie"] = ml_cookie

        try:
            # Se for link curto da Amazon, aproveita para expandir aqui e pegar o nome/imagem real
            if 'amzn.to' in url or 'link.amazon' in url:
                resp_expand = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
                url = resp_expand.url

            # Segue redirecionamentos para chegar na página real do produto
            resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            html = resp.text
            final_url = resp.url

            # Nome via meta tag (og:title ou twitter:title)
            if not name:
                meta_name = re.search(r'<meta[^>]+property=["\'](?:og:title|twitter:title)["\'][^>]+content=["\'](.*?)["\']', html)
                if not meta_name:
                    meta_name = re.search(r'<meta[^>]+name=["\'](?:og:title|twitter:title|title)["\'][^>]+content=["\'](.*?)["\']', html)
                
                if meta_name:
                    name = meta_name.group(1).split('|')[0].strip()
                else:
                    # Fallback para o <title> da página
                    title_match = re.search(r'<title>(.*?)</title>', html)
                    if title_match:
                        name = title_match.group(1).split(':')[0].strip()

            # Preço Shopee (centavos)
            if 'shopee' in final_url:
                price_matches = re.findall(r'"price":(\d{7,})', html)
                if price_matches:
                    price_val = int(price_matches[0]) / 100000
                    price = f"R$ {price_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            # Preço AliExpress (Geralmente em meta ou json)
            elif 'aliexpress' in final_url:
                price_match = re.search(r'["\']currencyCode["\']:["\']BRL["\'],["\']value["\']:(\d+\.?\d*)', html)
                if not price_match:
                    # Alternativa para preço no AliExpress
                    price_match = re.search(r'["\']amount["\']:["\'](\d+\.\d+)["\']', html)
                
                if price_match:
                    price_val = float(price_match.group(1))
                    price = f"R$ {price_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            # Preço Mercado Livre
            elif 'mercadolivre' in final_url:
                price_match = re.search(r'<meta[^>]+itemprop=["\']price["\'][^>]+content=["\'](\d+\.?\d*)["\']', html)
                if price_match:
                    price_val = float(price_match.group(1))
                    price = f"R$ {price_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            # Preço Amazon
            elif 'amazon' in final_url or 'link.amazon' in final_url:
                # Tenta várias classes comuns de preço na Amazon
                price_match = re.search(r'class=["\']a-offscreen["\']>(.*?)</span>', html)
                if price_match:
                    price = price_match.group(1).strip()
                else:
                    price_match = re.search(r'class=["\']a-price-whole["\']>(.*?)</span>', html)
                    if price_match:
                        price = f"R$ {price_match.group(1).strip()}"

            # Preço Magalu
            elif 'magazineluiza.com.br' in final_url or 'magalu.com' in final_url:
                # Tenta JSON de preço
                price_match = re.search(r'["\']price["\']:["\']?(\d+\.?\d*)["\']?', html)
                if not price_match:
                    price_match = re.search(r'class=["\']sc-[^>]+price-value["\']>(.*?)</span>', html)
                
                if price_match:
                    price_val = price_match.group(1).replace('R$', '').strip()
                    price = f"R$ {price_val}"

            # Imagem: tenta várias tags comuns (og:image, twitter:image, image_src)
            img_patterns = [
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\']+)["\']',
                r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\'](https?://[^"\']+)["\']',
                r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\'](https?://[^"\']+)["\']',
                r'["\']image["\']:["\'](https?://[^"\']+)["\']',
                r'["\']landingImage["\']:["\'](https?://[^"\']+)["\']', # Amazon especifico
                r'id=["\']landingImage["\'][^>]+src=["\'](https?://[^"\']+)["\']', # Amazon seletor
            ]
            
            for pattern in img_patterns:
                img_match = re.search(pattern, html)
                if img_match:
                    found_img = img_match.group(1).strip()
                    # Evita ícones de app ou logos genéricos se possível
                    if 'favicon' in found_img or 'logo' in found_img and image_url:
                        continue
                    image_url = found_img
                    # Limpeza para AliExpress
                    if 'aliexpress' in final_url and '_' in image_url:
                        image_url = image_url.split('_')[0]
                    
                    # Limpeza para Mercado Livre (Alta Resolução)
                    if 'mercadolivre' in final_url and '-O.jpg' in image_url:
                        image_url = image_url.replace('-O.jpg', '-F.jpg')
                    
                    # Limpeza para Amazon (Pegar imagem original sem redimensionamento)
                    if ('amazon' in final_url or 'link.amazon' in final_url) and '._AC_' in image_url:
                        image_url = re.sub(r'\._AC_.*?\.', '.', image_url)
                    
                    # Limpeza para Kabum (Geralmente já vem em boa resolução)
                    if 'kabum.com.br' in final_url and '?' in image_url:
                        image_url = image_url.split('?')[0]
                    
                    if image_url and not any(ext in image_url.lower() for ext in ['.jpg', '.png', '.webp', '.jpeg']):
                        image_url += '.jpg'
                    
                    break # Encontrou uma boa, para.

        except Exception as page_err:
            print(f"Aviso na página: {page_err}")

    except Exception as e:
        print(f"Erro get_product_info: {e}")

    print(f"Produto: {name} | Preço: {price} | Imagem: {bool(image_url)}")
    return name, image_url, price


# Links de loja que valem tentar baixar a imagem principal do produto
_RE_LINK_LOJA = re.compile(
    r'(?:amazon\.com\.br|amzn\.to|link\.amazon|aoferta\.net|shopee\.com\.br|s\.shopee|'
    r'mercadolivre|meli\.la|mlstatic|aliexpress\.com|s\.click\.ali|a\.aliexpress|'
    r'kabum\.com\.br|magazineluiza\.com\.br|magalu\.com|mgl\.io)',
    re.IGNORECASE,
)


def _extrair_imagem_da_pagina(html, final_url=''):
    """Extrai a URL da imagem principal (og:image, twitter:image, image_src ou
    data-a-dynamic-image da Amazon) a partir do HTML de uma página de produto."""
    if not html:
        return None
    # Amazon: imagem no atributo data-a-dynamic-image (JSON com URLs)
    m = re.search(r'data-a-dynamic-image="([^"]+)"', html)
    if m:
        import html as _html
        attr = _html.unescape(m.group(1))
        urls = re.findall(r'https://[^"]+?\.(?:jpg|jpeg|png|webp)', attr)
        if urls:
            img = urls[0]
            # Remove o sufixo de redimensionamento p/ pegar a imagem maior
            img = re.sub(r'\._[A-Z0-9_,]+_\.', '.', img)
            return img
    padroes = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\']+)["\']',
        r'<meta[^>]+content=["\'](https?://[^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\'](https?://[^"\']+)["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\'](https?://[^"\']+)["\']',
    ]
    for p in padroes:
        mm = re.search(p, html, re.IGNORECASE)
        if mm:
            img = mm.group(1).strip()
            if 'favicon' in img.lower() or 'logo' in img.lower():
                continue
            # Mercado Livre: prefere a versão de alta resolução
            if 'mlstatic' in img and '-O.' in img:
                img = img.replace('-O.', '-F.')
            # AliExpress: remove sufixo de tamanho (ex.: xxx_220x220.jpg)
            if 'alicdn' in img or 'aliexpress-media' in img:
                img = re.sub(r'_\d+x\d+(?=\.\w+$)', '', img)
            # KaBuM: usa a variante grande (_gg.jpg = ~1000px)
            if 'images.kabum.com.br' in img:
                img = re.sub(r'_[a-z]{1,2}\.(jpg|jpeg|png|webp)$', r'_gg.\1', img, flags=re.IGNORECASE)
            return img
    return None


def baixar_imagem_produto(texto, destino_dir):
    """Abre o primeiro link de loja encontrado em `texto`, extrai a imagem
    principal do produto e baixa para `destino_dir`. Retorna o caminho local
    ou None se não conseguir. Não quebra se falhar."""
    import time as _time
    if not texto or not destino_dir:
        return None
    try:
        os.makedirs(destino_dir, exist_ok=True)
    except Exception:
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    links = [l.rstrip('.,;|)') for l in re.findall(r'https?://\S+', texto or '')]
    # Só links de loja; ignora redes sociais/internos
    links = [l for l in links if _RE_LINK_LOJA.search(l)
             and not any(x in l for x in ('t.me/', 'instagram.com', 'facebook.com', 'links.andreindica'))]
    for link in links:
        try:
            # Shopee bloqueia scraping: a imagem vem pela API de afiliados
            if 'shopee' in link.lower():
                img_url = _shopee_image_url(link)
            elif 'aliexpress' in link.lower() or 's.click.ali' in link.lower():
                # AliExpress: tenta a API de afiliados (mais confiável); se
                # falhar, cai no scraping normal do og:image.
                img_url = _aliexpress_image_url(link)
                if not img_url:
                    resp = requests.get(link, headers=headers, timeout=15, allow_redirects=True)
                    img_url = _extrair_imagem_da_pagina(resp.text, resp.url)
            else:
                resp = requests.get(link, headers=headers, timeout=15, allow_redirects=True)
                if resp.status_code != 200:
                    continue
                img_url = _extrair_imagem_da_pagina(resp.text, resp.url)
            if not img_url:
                continue
            ri = requests.get(img_url, headers=headers, timeout=20)
            if ri.status_code != 200 or not ri.content:
                continue
            # Valida que é mesmo uma imagem
            try:
                from PIL import Image as _Image
                import io as _io
                _Image.open(_io.BytesIO(ri.content)).verify()
            except Exception:
                continue
            caminho = os.path.join(destino_dir, f'produto_{int(_time.time() * 1000)}.jpg')
            with open(caminho, 'wb') as f:
                f.write(ri.content)
            print(f"🖼️ Imagem do produto baixada: {img_url[:80]}")
            return caminho
        except Exception as err:
            print(f"Aviso ao baixar imagem do produto ({link[:50]}): {err}")
            continue
    return None


# Mapa loja -> arquivo de imagem fixa de cupom (pasta media/cupom/).
# Ordem importa: 'kabum' antes de 'aoferta'/'amazon' (o domínio aoferta.net
# serve Amazon E KaBuM; o sufixo '-Kabum' identifica a loja).
_CUPOM_POR_CHAVE = [
    ('shopee', 'cupom_shopee.jpg'),
    ('aliexpress', 'cupom_aliexpress.png'),
    ('ali express', 'cupom_aliexpress.png'),
    ('kabum', 'cupom_kabum.jpg'),
    ('mercado livre', 'cupom_mercado_livre.jpg'),
    ('mercadolivre', 'cupom_mercado_livre.jpg'),
    ('meli.la', 'cupom_mercado_livre.jpg'),
    ('magalu', 'cupom_magalu.png'),
    ('magazine', 'cupom_magalu.png'),
    ('amazon', 'cupom_amazon.jpg'),
    ('amzn', 'cupom_amazon.jpg'),
    ('aoferta', 'cupom_amazon.jpg'),
]


def imagem_cupom_loja(texto):
    """Retorna o caminho da imagem fixa de cupom da loja (pasta media/cupom/),
    detectada a partir do texto/links. None se não identificar a loja.
    Procura em media/cupom/ e em bot/static/bot/cupom/ (versionado)."""
    from bot.classifier import sem_acento
    t = sem_acento(texto or '').lower()
    for chave, arq in _CUPOM_POR_CHAVE:
        if chave in t:
            for base in (
                os.path.join(settings.MEDIA_ROOT, 'cupom'),
                os.path.join(settings.BASE_DIR, 'bot', 'static', 'bot', 'cupom'),
                os.path.join(settings.BASE_DIR, 'staticfiles', 'bot', 'cupom'),
            ):
                caminho = os.path.join(base, arq)
                if os.path.exists(caminho):
                    return caminho
    return None


def _shopee_image_url(link):
    """Obtém a imagem principal de um produto Shopee via API de afiliados
    (query productOfferV2). Retorna a URL da imagem ou None."""
    app_id = getattr(settings, 'SHOPEE_APP_ID', None)
    app_secret = getattr(settings, 'SHOPEE_SECRET', None)
    if not app_id or not app_secret:
        return None
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
        resp = requests.get(link, headers=headers, timeout=15, allow_redirects=True)
        final = resp.url or link
        m = re.search(r'-i\.(\d+)\.(\d+)', final)
        item_id = m.group(2) if m else None
        if not item_id:
            m2 = re.search(r'[?&]item[Ii]d=(\d+)', final)
            item_id = m2.group(1) if m2 else None
        if not item_id:
            return None
        timestamp = int(time.time())
        q = ('query{productOfferV2(itemId:%s,limit:1){nodes{imageUrl}}}' % item_id)
        body = json.dumps({"query": q}, separators=(',', ':'))
        signature = hashlib.sha256(f"{app_id}{timestamp}{body}{app_secret}".encode('utf-8')).hexdigest()
        hh = {
            "Content-Type": "application/json",
            "Authorization": f"SHA256 Credential={app_id},Timestamp={timestamp},Signature={signature}",
        }
        r = requests.post("https://open-api.affiliate.shopee.com.br/graphql", headers=hh, data=body, timeout=20)
        nodes = r.json().get('data', {}).get('productOfferV2', {}).get('nodes') or []
        if nodes:
            return nodes[0].get('imageUrl')
    except Exception as err:
        print(f"Aviso na imagem Shopee: {err}")
    return None


def _aliexpress_image_url(link):
    """Obtém a imagem principal de um produto AliExpress via API de afiliados
    (method aliexpress.affiliate.productdetail.get). Retorna a URL ou None."""
    app_key = getattr(settings, 'ALIEXPRESS_APP_KEY', None)
    app_secret = getattr(settings, 'ALIEXPRESS_APP_SECRET', None)
    if not app_key or not app_secret:
        return None
    # Descobre o product_id (resolvendo redirect quando for link curto)
    pid = None
    m = re.search(r'/item/(\d+)', link)
    if m:
        pid = m.group(1)
    else:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
            resp = requests.get(link, headers=headers, timeout=15, allow_redirects=True)
            m = re.search(r'/item/(\d+)', resp.url or '')
            if m:
                pid = m.group(1)
        except Exception:
            pass
    if not pid:
        return None
    for _tent in range(3):
        try:
            params = {
                'app_key': app_key,
                'method': 'aliexpress.affiliate.productdetail.get',
                'format': 'json', 'v': '2.0', 'sign_method': 'md5',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
                'product_ids': pid, 'target_currency': 'BRL', 'target_language': 'PT',
                'tracking_id': getattr(settings, 'ALIEXPRESS_TRACKING_ID', '') or '',
            }
            s = app_secret + ''.join(f'{k}{params[k]}' for k in sorted(params)) + app_secret
            params['sign'] = hashlib.md5(s.encode()).hexdigest().upper()
            ar = requests.get("https://api-sg.aliexpress.com/sync", params=params, timeout=25)
            j = ar.json()
            if 'error_response' in j:
                # Rate limit costuma ser temporário: aguarda e tenta de novo
                time.sleep(4)
                continue
            resp = j.get('aliexpress_affiliate_productdetail_get_response', {})
            result = resp.get('resp_result', {}).get('result', {})
            prods = result.get('products', {})
            if isinstance(prods, dict):
                prods = prods.get('product', [])
            if prods:
                return prods[0].get('product_main_image_url')
            return None
        except Exception:
            time.sleep(2)
    return None


import urllib.parse

def convert_to_affiliate_link(url, final_url=None):
    """
    Decide qual API usar com base na URL.
    """
    # URLs encurtadas que NÃO identificam a loja pelo domínio (ex.:
    # aoferta.net → Amazon.com.br) precisam ser expandidas primeiro, senão
    # o roteamento abaixo não reconhece a loja e retorna None.
    if 'aoferta.net' in url or 'aoferta.net/' in url:
        try:
            resp = requests.get(
                url,
                allow_redirects=True,
                timeout=12,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                },
            )
            if resp.url:
                url = resp.url
        except Exception:
            pass
    if 'shopee.com.br' in url or 's.shopee' in url:
        # Se for um link de afiliado (s.shopee.com.br/an_redir ou an_redir),
        # extrai o origin_link que contém a URL pura do produto.
        if 'an_redir' in url or 'affiliate_id=' in url:
            try:
                from urllib.parse import urlparse, parse_qs, unquote
                qs = parse_qs(urlparse(url).query)
                origin = qs.get('origin_link', [''])[0]
                if origin:
                    url = unquote(origin)
            except Exception:
                pass
        return convert_shopee_link(url)
    elif 'aliexpress.com' in url or 's.click.aliexpress' in url:
        return convert_aliexpress_link(url)
    elif 'amazon.com.br' in url or 'amzn.to' in url or 'link.amazon' in url:
        return convert_amazon_link(url)
    elif 'mercadolivre.com' in url or 'meli.la' in url or 'mlstatic.com' in url or 'mercadolibre.com' in url:
        return convert_mercado_livre_link(url)
    elif 'kabum.com.br' in url or 'tidd.ly' in url:
        return convert_awin_link(url, merchant_id='17729') # Kabum MID padrao
    elif 'magazineluiza.com.br' in url or 'magalu.com' in url or 'mgl.io' in url or 'divulgador.magalu.com' in url:
        return convert_magalu_link(url)
    return None


def convert_mercado_livre_link(url):
    """
    Converte link do Mercado Livre para afiliado.
    - Se já tem slug completo: monta o link direto sem requisição.
    - meli.la / /social/: extrai o produto principal combinando card-featured,
      bloco JSON via og:image, produto.mercadolivre.../_JM e fallback seguro mutando URL social.
    - Suporte a encurtamento meli.la oficial via cookie se configurado.
    """
    tag = getattr(settings, 'MERCADO_LIVRE_TAG', 'pean3412407')
    matt_tool = getattr(settings, 'MERCADO_LIVRE_MATT_TOOL', '57756886')
    ml_cookie = getattr(settings, 'MERCADO_LIVRE_COOKIE', None)

    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }
    if ml_cookie:
        hdrs["Cookie"] = ml_cookie

    try:
        import re as _re

        # 1) Se já tem slug no link (ex: /produto/p/MLB... ou /produto/up/MLBU...), usa direto
        m = _re.search(r'https://www\.mercadolivre\.com\.br/([^/\s]+)/((?:p/MLB\d+|up/MLBU\d+))', url)
        if m:
            slug = m.group(1)
            item_path = m.group(2)
            affiliate_url = f"https://www.mercadolivre.com.br/{slug}/{item_path}?matt_tool={matt_tool}&matt_word={tag}"
            print(f"ML Afiliado (já tem slug): {affiliate_url[:130]}...")
            return affiliate_url

        # 2) Se é meli.la OU /social/ → busca página e extrai o produto principal
        if 'meli.la' in url or '/social/' in url:
            r = requests.get(url, allow_redirects=True, timeout=12, headers=hdrs)
            final_url = r.url
            page_html = r.text

            if '/social/' in final_url:
                # 2a) Prioridade 1: Identificador 'card-featured' da página social
                featured_links = _re.findall(
                    r'href=["\'](https://www\.mercadolivre\.com\.br/[^"\']*card-featured[^"\']*)',
                    page_html,
                )
                if featured_links:
                    produto_url = featured_links[0].split('?')[0].split('#')[0]
                    affiliate_url = f"{produto_url}?matt_tool={matt_tool}&matt_word={tag}"
                    print(f"ML Afiliado (social card-featured): {affiliate_url[:130]}...")
                    return affiliate_url

                # 2b) Prioridade 2 (lógica afiliado_ofertas): busca via og:image e bloco JSON
                unesc = page_html.replace('\\u002F', '/').replace('\\u0022', '"')
                og_img = _re.search(r'og:image[^>]*content="([^"]*)"', page_html, _re.IGNORECASE)
                main_img_id = None
                if og_img:
                    m_img = _re.search(r'MLB\d+', og_img.group(1))
                    main_img_id = m_img.group(0) if m_img else None

                main_block = None
                if main_img_id:
                    idx = unesc.find(main_img_id, 20000)
                    if idx == -1:
                        idx = unesc.find(main_img_id)
                    if idx != -1:
                        main_block = unesc[max(0, idx - 6000):idx + 3000]

                if main_block:
                    # Prefere URL www.mercadolivre.../slug/(p|up)/MLB... dentro do bloco principal
                    m_block = _re.search(r'www\.mercadolivre\.com\.br/([^/\s"]+)/((?:p/MLB|up/MLBU)(\d+))', main_block)
                    if m_block:
                        slug = m_block.group(1)
                        item_path = m_block.group(2)
                        affiliate_url = f"https://www.mercadolivre.com.br/{slug}/{item_path}?matt_tool={matt_tool}&matt_word={tag}"
                        print(f"ML Afiliado (social bloco principal): {affiliate_url[:130]}...")
                        return affiliate_url

                    # Anúncio comum: produto.mercadolivre.com.br/MLB-XXXX-slug-_JM
                    old = _re.search(r'produto\.mercadolivre\.com\.br/(MLB-(\d+)-[^"_\s]+(?:_[^"_\s]+)*_JM)', main_block)
                    if old:
                        old_path = old.group(1)
                        affiliate_url = f"https://produto.mercadolivre.com.br/{old_path}?matt_tool={matt_tool}&matt_word={tag}"
                        print(f"ML Afiliado (social item _JM): {affiliate_url[:130]}...")
                        return affiliate_url

                    # pdp_filters item_id + sanitized_title
                    pdp = _re.search(r'item_id%3A(MLB\d+)', main_block)
                    st = _re.search(r'sanitized_title":"-?([^"]+)"', main_block)
                    if pdp and st:
                        mlb_id = pdp.group(1)
                        slug = st.group(1).strip('-')
                        affiliate_url = f"https://www.mercadolivre.com.br/{slug}/p/{mlb_id}?matt_tool={matt_tool}&matt_word={tag}"
                        print(f"ML Afiliado (social pdp): {affiliate_url[:130]}...")
                        return affiliate_url

                # 2c) Fallback: primeira URL com slug do feed
                first_match = _re.search(r'www\.mercadolivre\.com\.br/([^/\s"]+)/((?:p/MLB|up/MLBU)(\d+))', unesc)
                if first_match:
                    slug = first_match.group(1)
                    item_path = first_match.group(2)
                    affiliate_url = f"https://www.mercadolivre.com.br/{slug}/{item_path}?matt_tool={matt_tool}&matt_word={tag}"
                    print(f"ML Afiliado (social feed slug): {affiliate_url[:130]}...")
                    return affiliate_url

                # 2d) Fallback infalível do afiliado_ofertas: muta parâmetros matt na própria URL social
                try:
                    import urllib.parse as _urlparse
                    parsed = _urlparse.urlparse(r.url)
                    qs = dict(_urlparse.parse_qsl(parsed.query, keep_blank_values=True))
                    qs['matt_word'] = tag
                    qs['matt_tool'] = str(matt_tool)
                    new_qs = _urlparse.urlencode(qs)
                    affiliate_url = _urlparse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_qs, parsed.fragment))
                    print(f"ML Afiliado (social fallback seguro): {affiliate_url[:130]}...")
                    return affiliate_url
                except Exception:
                    pass

            # Se o redirect foi para uma URL de produto direta
            if 'mercadolivre.com.br' in final_url and '/social/' not in final_url:
                clean_final = final_url.split('?')[0].split('#')[0]
                if '/p/MLB' in clean_final or '/up/MLBU' in clean_final or '/MLB' in clean_final:
                    affiliate_url = f"{clean_final}?matt_tool={matt_tool}&matt_word={tag}"
                    print(f"ML Afiliado (redirect direto): {affiliate_url[:130]}...")
                    return affiliate_url

        # 3) Links bare /p/MLB... ou /up/MLBU... sem slug
        if '/p/MLB' in url or '/up/MLBU' in url:
            print(f"ML: Link sem slug detectado ({url}) — ML bloqueia sem slug.")
            return None

        print("ML: Formato de link não suportado")
        return None

    except Exception as e:
        print(f"ML: Erro na conversão ({e})")
        return None


def convert_awin_link(url, merchant_id='17729'):
    """
    Gera link de afiliado Awin. Limpa a URL da Kabum para evitar bugs de tela preta
    e links gigantes com rastreios de terceiros.
    """
    publisher_id = getattr(settings, 'AWIN_PUBLISHER_ID', '1670083')
    api_token = getattr(settings, 'AWIN_API_TOKEN', None)

    # 1. Expandir links curtos (tidd.ly) para pegar a URL real
    if 'tidd.ly' in url:
        try:
            resp = requests.get(url, allow_redirects=True, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            url = resp.url
        except Exception as e:
            print(f"Awin: Erro ao expandir: {e}")

    # 2. LIMPEZA PROFUNDA: Extrair apenas o link essencial da Kabum
    # Aceita tanto /produto/ID/NOME quanto apenas /produto/ID
    kabum_match = re.search(r'(https?://(?:www\.)?kabum\.com\.br/produto/\d+(?:/[^/?\s]+)?)', url)
    if kabum_match:
        url = kabum_match.group(1)
    elif 'kabum.com.br' in url:
        url = url.split('?')[0]

    # 3. Tentar encurtar via API (Tidd.ly)
    if api_token:
        try:
            endpoint = f"https://api.awin.com/publishers/{publisher_id}/link-generator"
            headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}
            payload = {
                "destinationUrl": url,
                "advertiserId": int(merchant_id),
                "shorten": True
            }
            response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
            res_data = response.json()
            short_url = res_data.get("shortUrl")
            if short_url:
                print(f"Awin API Sucesso: {short_url}")
                return short_url
            else:
                print(f"Awin API falhou em encurtar: {res_data}")
        except Exception as e:
            print(f"Erro Awin API: {e}")

    # 4. Fallback: Formato correto confirmado pela API da Awin (awclick.php)
    encoded_url = urllib.parse.quote(url, safe=':/')
    return f"https://www.awin1.com/awclick.php?mid={merchant_id}&id={publisher_id}&ued={encoded_url}"



def convert_magalu_link(url):
    """
    Gera link de afiliado Parceiro Magalu (magazinevoce) de forma infalivel.
    Usa o formato direto de PID que evita erros de slug/404.
    """
    magalu_id = getattr(settings, 'MAGALU_ID', 'magazinein_1546179')
    
    # 1. Expandir links curtos (Magalu mobile/divulgador costuma ser teimoso)
    if any(domain in url for domain in ['mgl.io', 'divulgador.magalu.com', 'magalu.com', 'bit.ly']):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            resp = requests.get(url, allow_redirects=True, timeout=12, headers=headers)
            url = resp.url
        except:
            pass

    # 2. Se ja for magazinevoce, apenas troca o ID
    if 'magazinevoce.com.br' in url:
        return re.sub(r'magazinevoce\.com\.br/[^/]+', f'magazinevoce.com.br/{magalu_id}', url)

    # 3. Extrair o Código do Produto (PID) - O metodo mais seguro
    # Padrao: /p/ID/ ou /produto/ID/
    pid_match = re.search(r'/(?:p|produto)/([a-zA-Z0-9]+)', url)
    
    if pid_match:
        pid = pid_match.group(1)
        # O formato /LOJA/p/ID/ e o que menos da erro 404
        return f"https://www.magazinevoce.com.br/{magalu_id}/p/{pid}/"

    # 4. Caso nao ache o /p/, tenta pegar pelo caminho limpo (Slug)
    match_path = re.search(r'(?:magazineluiza\.com\.br|magalu\.com\.br|magalu\.com)/([^/?]+)', url)
    if match_path:
        slug = match_path.group(1).strip('/')
        if len(slug) > 5:
            return f"https://www.magazinevoce.com.br/{magalu_id}/{slug}/p/produto/"

    # 5. Fallback Final: Link de redirecionamento oficial da Magalu
    # Este link forca o redirecionamento correto com o seu ID
    encoded_url = urllib.parse.quote(url)
    return f"https://www.magazineluiza.com.br/selecao/produtos/?magalu_id={magalu_id}&url={encoded_url}"


def convert_amazon_link(url):
    """
    Gera link de afiliado Amazon injetando a TAG.
    """
    tag = getattr(settings, 'AMAZON_ASSOCIATE_TAG', 'andre0cda-20')
    
    # Se for link curto da Amazon, precisamos expandir para pegar o ID do produto
    if 'amzn.to' in url or 'link.amazon' in url:
        try:
            resp = requests.get(url, allow_redirects=True, timeout=5)
            url = resp.url
        except:
            pass
            
    # Limpa a URL de tags antigas e adiciona a sua
    clean_url = url.split('?')[0]
    return f"{clean_url}?tag={tag}"




def convert_shopee_link(url):
    """API Shopee"""
    app_id = settings.SHOPEE_APP_ID
    app_secret = settings.SHOPEE_SECRET
    if not app_id or not app_secret: return None

    endpoint = "https://open-api.affiliate.shopee.com.br/graphql"
    timestamp = int(time.time())
    graphql_query = 'mutation{generateShortLink(input:{originUrl:"' + url + '"}){shortLink}}'
    query = {"query": graphql_query}
    body = json.dumps(query, separators=(',', ':'))
    payload = f"{app_id}{timestamp}{body}{app_secret}"
    signature = hashlib.sha256(payload.encode('utf-8')).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id},Timestamp={timestamp},Signature={signature}"
    }

    try:
        response = requests.post(endpoint, headers=headers, data=body)
        res = response.json().get('data', {}).get('generateShortLink', {})
        return res.get('shortLink')
    except:
        return None


def convert_aliexpress_link(url, base_on_clean_url=False):
    """API AliExpress"""
    app_key = settings.ALIEXPRESS_APP_KEY
    app_secret = settings.ALIEXPRESS_APP_SECRET
    tracking_id = settings.ALIEXPRESS_TRACKING_ID
    if not app_key or not app_secret: return None

    # Se solicitado (para o link de PC), tentamos pegar a URL real do produto para evitar o fluxo de Moedas do App
    final_url = url
    if base_on_clean_url and ('s.click.aliexpress' in url or 'a.aliexpress.com' in url or 'aliexpress.com/item' not in url):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
            resp = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            # Pegamos apenas a base da URL antes das interrogações para ser o mais "limpa" possível
            final_url = resp.url.split('?')[0] if '?' in resp.url else resp.url
        except:
            pass

    endpoint = "https://api-sg.aliexpress.com/sync"
    params = {
        "app_key": app_key,
        "format": "json",
        "method": "aliexpress.affiliate.link.generate",
        "sign_method": "md5",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "v": "2.0",
        "promotion_link_type": "0",
        "source_values": final_url,
        "tracking_id": tracking_id
    }

    # Gerar Assinatura MD5 AliExpress
    sorted_keys = sorted(params.keys())
    sign_str = app_secret
    for key in sorted_keys:
        sign_str += f"{key}{params[key]}"
    sign_str += app_secret
    params["sign"] = hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

    try:
        response = requests.get(endpoint, params=params)
        data = response.json()
        result = data.get("aliexpress_affiliate_link_generate_response", {}).get("resp_result", {}).get("result", {})
        links = result.get("promotion_links", {}).get("promotion_link", [])
        if links:
            return links[0].get("promotion_link")
    except Exception as e:
        print(f"Erro AliExpress API: {e}")
        return None


def send_whatsapp_message(text, image_path=None):
    """
    Envia mensagem para o WhatsApp via Evolution API v2.
    Formato correto: JSON com base64 no campo 'media' (sem wrapper 'mediaMessage').
    """
    import os
    import base64

    url_base = getattr(settings, 'EVOLUTION_API_URL', '').strip('/')
    instance = getattr(settings, 'EVOLUTION_API_INSTANCE', '')
    token = getattr(settings, 'EVOLUTION_API_TOKEN', '')
    jid = getattr(settings, 'WHATSAPP_GROUP_JID', '')

    if not all([url_base, instance, token, jid]) or jid == 'seu_jid_do_grupo_aqui@g.us':
        print("WhatsApp: Credenciais ou JID não configurados.")
        return False

    headers = {
        "apikey": token,
        "Content-Type": "application/json"
    }

    try:
        if image_path and os.path.exists(image_path):
            # Evolution Go: envia imagem em base64 no campo 'url' (v0.7.0+)
            endpoint = f"{url_base}/send/media"
            with open(image_path, "rb") as img_file:
                b64 = base64.b64encode(img_file.read()).decode('utf-8')

            payload = {
                "number": jid,
                "caption": text,
                "type": "image",
                "mimetype": "image/jpeg",
                "url": b64
            }
            response = requests.post(endpoint, headers=headers, json=payload, timeout=40)
            print(f"WhatsApp (imagem) Status: {response.status_code} - {response.text[:200]}")

        elif image_path and image_path.startswith('http'):
            # Envio via URL pública
            endpoint = f"{url_base}/send/media"
            payload = {
                "number": jid,
                "caption": text,
                "type": "image",
                "mimetype": "image/jpeg",
                "url": image_path
            }
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            print(f"WhatsApp (url) Status: {response.status_code} - {response.text[:200]}")

        else:
            # Apenas texto
            endpoint = f"{url_base}/send/text"
            payload = {
                "number": jid,
                "text": text
            }
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            print(f"WhatsApp (texto) Status: {response.status_code}")

        return response.status_code in [200, 201]
    except Exception as e:
        print(f"Erro crítico no WhatsApp: {e}")
        return False


def normalizar_whatsapp(numero):
    """
    Normaliza um número de WhatsApp para o formato internacional +55DDDNUMERO.
    Remove símbolos/espaços e garante o prefixo +55 (o usuário digita só DDD+número,
    ex.: '38 999821883' -> '+5538999821883').
    """
    if not numero:
        return ''
    digitos = re.sub(r'\D', '', str(numero))
    if digitos.startswith('55') and len(digitos) >= 12:
        return '+' + digitos
    return '+55' + digitos


def send_whatsapp_to_user(numero, text, image_path=None):
    """
    Envia mensagem de WhatsApp para um NÚMERO específico (conta individual),
    via Evolution API. Difere do send_whatsapp_message (que envia para o grupo).
    """
    import os
    import base64

    url_base = getattr(settings, 'EVOLUTION_API_URL', '').strip('/')
    instance = getattr(settings, 'EVOLUTION_API_INSTANCE', '')
    token = getattr(settings, 'EVOLUTION_API_TOKEN', '')

    if not all([url_base, instance, token]):
        print("WhatsApp: credenciais não configuradas.")
        return False

    number = normalizar_whatsapp(numero)
    if not number:
        print("WhatsApp: número inválido.")
        return False

    headers = {
        "apikey": token,
        "Content-Type": "application/json"
    }

    try:
        if image_path and (isinstance(image_path, str) and image_path.startswith('http')):
            # Envio via URL pública da imagem
            endpoint = f"{url_base}/send/media"
            payload = {
                "number": number,
                "caption": text,
                "type": "image",
                "mimetype": "image/jpeg",
                "url": image_path
            }
            response = requests.post(endpoint, headers=headers, json=payload, timeout=40)
            print(f"WhatsApp usuário {number} (url) Status: {response.status_code} - {response.text[:120]}")
            return response.status_code in [200, 201]

        if image_path and os.path.exists(image_path):
            # Envio via base64 (arquivo local)
            endpoint = f"{url_base}/send/media"
            with open(image_path, "rb") as img_file:
                b64 = base64.b64encode(img_file.read()).decode('utf-8')
            payload = {
                "number": number,
                "caption": text,
                "type": "image",
                "mimetype": "image/jpeg",
                "url": b64
            }
            response = requests.post(endpoint, headers=headers, json=payload, timeout=40)
            print(f"WhatsApp usuário {number} (imagem) Status: {response.status_code} - {response.text[:120]}")
            return response.status_code in [200, 201]

        # Apenas texto
        endpoint = f"{url_base}/send/text"
        payload = {
            "number": number,
            "text": text
        }
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        print(f"WhatsApp usuário {number} Status: {response.status_code} - {response.text[:120]}")
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"Erro ao enviar WhatsApp individual: {e}")
        return False


def extract_links(text):
    return re.findall(r'(https?://\S+)', text)


def strip_promo_footer(text):
    """
    Remove rodapés promocionais/copys que não devem ser reenviados pelo bot.
    """
    channel_name = getattr(settings, 'PERSONAL_CHANNEL_NAME', 'Seu Canal')
    escaped_channel_name = re.escape(channel_name)

    cleaned_text = re.sub(
        rf'(?im)^\s*{escaped_channel_name}(?:\s+promos?)?\s*$',
        '',
        text,
    )
    cleaned_text = re.sub(r'(?im)^\s*telegram\s*:\s*\S+\s*$', '', cleaned_text)
    cleaned_text = re.sub(r'(?im)^\s*whatsapp\s*:\s*\S+\s*$', '', cleaned_text)
    cleaned_text = re.sub(r'(?im)^\s*#an[uú]ncio\s*$', '', cleaned_text)
    cleaned_text = re.sub(r'(?im)^\s*🤫\s*➡️\s*Link\s+Geral.*$', '', cleaned_text)
    cleaned_text = re.sub(r'(?im)^\s*https?://links\.andreindica\.com\.br/?\s*$', '', cleaned_text)
    cleaned_text = re.sub(r'(?im)^\s*‼️\s*Bot\s+de\s+alerta\s*:\s*@\S+\s*$', '', cleaned_text)
    # PEPERAIO: remove linhas do rodapé de alertas (ex.: '🔔 BOT DE ALERTAS: pode retirar ...')
    cleaned_text = re.sub(r'(?im)^\s*🔔?\s*Bot\s+de\s+alertas?\s*:.*$', '', cleaned_text)
    # PC DO FAFA: remove rodapés e textos de verificação do canal
    cleaned_text = re.sub(r'(?im)^\s*✅\s*BOT\s+DE\s+DESCONTOS\s*:\s*@\S+\s*$', '', cleaned_text)
    cleaned_text = re.sub(r'(?im)^\s*✅\s*Oferta\s+verificada\s*:.*$', '', cleaned_text)
    # TecnoArt: remove o bloco de divulgação dos outros canais
    # ('⚡️SE LIGA NOS OUTROS CANAIS DO TECNOART⚡️' + '👨🏼‍💻SÓ PLACAS DE VÍDEO: ...')
    cleaned_text = re.sub(r'(?im)^[^\n]*se\s+liga\s+nos\s+outros\s+canais[^\n]*$', '', cleaned_text)
    cleaned_text = re.sub(
        r'(?im)^[^\n]*\bs[oó]\s+(?:placas?|notebooks?|smart\w*|celulares?|'
        r'perif[eé]ricos?|monitores?|tvs?|games?|processadores?|mem[oó]rias?|'
        r'hardwares?|ofertas?)\b[^\n]*$',
        '', cleaned_text,
    )
    # Remove a marca '(anuncio)'/'(anúncio)' isolada
    cleaned_text = re.sub(r'(?im)^\s*\(\s*an[uú]ncio\s*\)\s*$', '', cleaned_text)
    # AliExpress/canais: remove linhas de divulgação de BOTS (ex.: '💰 Bot de
    # Moedas: https://cutt.ly/...', '⭐ Bot de descontos AliExpress: ...').
    cleaned_text = re.sub(r'(?im)^[^\n]*\bbot\s+de\s+(?:moedas?|descontos?|desconto)\b[^\n]*$', '', cleaned_text)
    # E remove o LINK curto (cutt.ly/bit.ly) que fica sozinho na linha seguinte
    # do bot (ex.: '💰 Bot de Moedas:\nhttps://cutt.ly/VybzLI4W').
    cleaned_text = re.sub(
        r'(?im)^\s*https?://(?:cutt\.ly|bit\.ly|tinyurl\.com|rebrand\.ly)/\S*\s*$',
        '', cleaned_text,
    )
    cleaned_text = re.sub(r'(?im)^\s*_{5,}\s*$', '', cleaned_text)
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
    return cleaned_text.strip()


_RE_EMOJI_ALL = re.compile(
    r'[\U0001F000-\U0001FAFF]'
    r'|[\u2600-\u27BF]'
    r'|[\u2190-\u21FF]'
    r'|[\u2B00-\u2BFF]'
    r'|\ufe0f|\u200d|\u00a9|\u00ae|\u2122|\u00a0',
)

def normaliza_emoji_inicial(texto):
    """Troca o PRIMEIRO emoji da mensagem capturada por um emoji de alerta
    escolhido aleatoriamente. Os demais emojis e o restante do texto são
    preservados. Também limpa espaços/quebras de linha excedentes.

    Lista de emojis de alerta:
        🚨 ⚠️ 🔔 📢 📣 ‼️ ❗ ❕ 🔥 ⚡ 👀 🛎️ 🚩 🆘 ⛔ 🛑 🔴 🟠 💥 📍
    """
    import random

    _EMOJIS_ALERTA = [
        '🚨', '⚠️', '🔔', '📢', '📣', '‼️', '❗', '❕',
        '🔥', '⚡', '👀', '🛎️', '🚩', '🆘', '⛔', '🛑',
        '🔴', '🟠', '💥', '📍',
    ]

    if not texto:
        return texto
    t = texto.strip()
    if not t:
        return texto

    # Limpa espaços excedentes em cada linha
    linhas = []
    for linha in t.split('\n'):
        linhas.append(re.sub(r'[ \t]+', ' ', linha).strip())
    t = '\n'.join(linhas)
    t = re.sub(r'\n{3,}', '\n\n', t).strip()

    # Encontra e substitui o PRIMEIRO emoji da mensagem
    # A regex captura qualquer emoji (bloco de caracteres Unicode gráficos)
    primeiro_emoji_re = re.compile(
        r'^(\s*)'                       # espaços/quebras iniciais (grupo 1)
        r'((?:[\U0001F000-\U0001FFFF]'  # emojis suplementares
        r'|[\U00002600-\U000027FF]'     # símbolos miscelâneos
        r'|[\U00002B00-\U00002BFF]'     # setas / símbolos
        r'|[\U00003000-\U00003300]'     # CJK e cercados
        r'|[\u00A9\u00AE\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9-\u21AA]'
        r'|[\u231A-\u231B\u2328\u23CF\u23E9-\u23F3\u23F8-\u23FA]'
        r'|[\u25AA-\u25AB\u25B6\u25C0\u25FB-\u25FE\u2600-\u2604\u260E]'
        r'|[\u2611\u2614-\u2615\u2618\u261D\u2620\u2622-\u2623\u2626]'
        r'|[\u262A\u262E-\u262F\u2638-\u263A\u2640\u2642\u2648-\u2653]'
        r'|[\u265F-\u2660\u2663\u2665-\u2666\u2668\u267B\u267E-\u267F]'
        r'|[\u2692-\u2697\u2699\u269B-\u269C\u26A0-\u26A1\u26A7]'
        r'|[\u26AA-\u26AB\u26B0-\u26B1\u26BD-\u26BE\u26C4-\u26C5]'
        r'|[\u26CE-\u26CF\u26D1\u26D3-\u26D4\u26E9-\u26EA\u26F0-\u26F5]'
        r'|[\u26F7-\u26FA\u26FD\u2702\u2705\u2708-\u270D\u270F]'
        r'|[\u2712\u2714\u2716\u271D\u2721\u2728\u2733-\u2734\u2744]'
        r'|[\u2747\u274C\u274E\u2753-\u2755\u2757\u2763-\u2764]'
        r'|[\u2795-\u2797\u27A1\u27B0\u27BF\u2934-\u2935\u2B05-\u2B07]'
        r'|[\u2B1B-\u2B1C\u2B50\u2B55\u3030\u303D\u3297\u3299]'
        r')[\uFE0F\u20E3]?'             # modificador opcional (VS-16 / keycap)
        r'(?:\u200D(?:[\U0001F000-\U0001FFFF][\uFE0F]?))*'  # ZWJ sequences
        r')+',                          # um ou mais emojis/seqs colados
        re.DOTALL,
    )

    novo_emoji = random.choice(_EMOJIS_ALERTA)
    m = primeiro_emoji_re.match(t)
    if m:
        # Substitui apenas o bloco de emojis inicial pelo sorteado
        t = novo_emoji + ' ' + t[m.end():].lstrip()
    else:
        # Mensagem sem emoji no início: insere o emoji sorteado no começo
        t = novo_emoji + ' ' + t

    return t



async def process_offer_to_group(bot_app, text, photo=None):
    """
    Processa uma oferta (texto + foto opcional), converte links e posta no grupo.
    bot_app: Instância do bot do Telegram (Bot ou Application)
    """
    if not text:
        return False

    # Filtro: Ignora links da Terabyte
    if 'terabyte' in text.lower() or 'terabyteshop' in text.lower():
        print("ℹ️ Oferta da Terabyte ignorada.")
        return False

    # Detecta se é o Application ou o Bot direto para saber qual objeto usar
    bot = getattr(bot_app, 'bot', bot_app)

    links = extract_links(text)
    if not links:
        return False

    modified_text = text
    original_link = None
    converted_any = False

    # 1. Substituições de Links e Nomes (Canais de terceiros)
    personal_link = getattr(settings, 'PERSONAL_CHANNEL_LINK', '')
    channel_name = getattr(settings, 'PERSONAL_CHANNEL_NAME', 'Seu Canal')
    
    # Limpa nomes de outros canais
    modified_text = re.sub(r'(?i)zFinnY|Iskandar|CaCau|André Indica|Tecnan|PC DO FAFA', channel_name, modified_text)

    # Substitui links do Linktree pelo link personalizado
    modified_text = re.sub(r'https?://linktr\.ee/\S+', 'https://links.andreindica.com.br/', modified_text)
    modified_text = strip_promo_footer(modified_text)

    has_aliexpress = False
    for link in links:
        is_shopee = 'shopee.com.br' in link or 's.shopee' in link
        is_aliexpress = 'aliexpress.com' in link or 's.click.aliexpress' in link
        is_ml = 'mercadolivre.com' in link or 'mlstatic.com' in link or 'mercadolivre.com.br' in link
        is_amazon = 'amazon.com.br' in link or 'amzn.to' in link or 'link.amazon' in link
        is_kabum = 'kabum.com.br' in link or 'tidd.ly' in link
        is_magalu = 'magazineluiza.com.br' in link or 'magalu.com' in link or 'mgl.io' in link
        is_telegram = 't.me/' in link
        is_tecnan = 'tecnan.com.br' in link

        if is_telegram or is_tecnan:
            if personal_link and personal_link not in link:
                modified_text = modified_text.replace(link, personal_link)
                converted_any = True
            continue

        is_awin = 'awin1.com' in link or 'tidd.ly' in link

        if is_awin:
            # Extrai a URL real do produto do parâmetro 'ued' e gera novo link com nosso ID
            extracted_url = None
            if 'ued=' in link:
                try:
                    ued_value = link.split('ued=')[1].split('&')[0]
                    extracted_url = urllib.parse.unquote(ued_value)
                except:
                    pass
            if not extracted_url and 'tidd.ly' in link:
                try:
                    resp = requests.get(link, allow_redirects=True, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
                    if 'kabum.com.br' in resp.url:
                        extracted_url = resp.url
                except:
                    pass
            if extracted_url:
                new_awin = convert_awin_link(extracted_url)
                if new_awin:
                    modified_text = modified_text.replace(link, new_awin)
                    original_link = extracted_url
                    converted_any = True
                    continue
            # Fallback: considera como convertido para não bloquear
            converted_any = True
            original_link = link
            continue

        if not any([is_shopee, is_aliexpress, is_ml, is_amazon, is_kabum, is_magalu]):
            # Canal PC DO FAFA: links vêm como redirecionamento em pcdofafa.com.br.
            # A página faz redirect via <meta http-equiv="refresh"> com delay 0;
            # extrai esse destino e converte para afiliado.
            if 'pcdofafa.com.br' in link:
                try:
                    resp = requests.get(
                        link,
                        allow_redirects=True,
                        timeout=8,
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    html = resp.text
                    real_url = ''
                    m = re.search(
                        r'http-equiv=["\']refresh["\']\s+content=["\']\d+;\s*url=([^"\']+)',
                        html,
                        re.IGNORECASE,
                    )
                    if m:
                        real_url = m.group(1).strip()
                    if not real_url:
                        # Fallback: procura qualquer link de loja conhecida no HTML
                        m2 = re.search(
                            r'https?://(?:a\.|s\.click\.|pt\.)?aliexpress\.com/[^\s"<>]+'
                            r'|https?://[^\s"<>]*shopee\.com[^\s"<>]+'
                            r'|https?://[^\s"<>]*mercadolivre\.com[^\s"<>]+'
                            r'|https?://[^\s"<>]*amazon\.com\.br[^\s"<>]+'
                            r'|https?://[^\s"<>]*kabum\.com\.br[^\s"<>]+'
                            r'|https?://[^\s"<>]*magalu[^\s"<>]+',
                            html,
                            re.IGNORECASE,
                        )
                        if m2:
                            real_url = m2.group(0)
                    if real_url:
                        print(f"PC DO FAFA redirect: {link} -> {real_url}")
                        converted = convert_to_affiliate_link(real_url)
                        if converted:
                            modified_text = modified_text.replace(link, converted)
                            converted_any = True
                            original_link = link
                            continue
                except Exception as fafa_err:
                    print(f"PC DO FAFA expand erro: {fafa_err}")
            continue

        print(f"Convertendo link: {link}")
        converted = convert_to_affiliate_link(link)
        if converted:
            original_link = link
            if is_aliexpress:
                has_aliexpress = True
                link_app = converted
                link_pc = convert_aliexpress_link(link, base_on_clean_url=True)
                # Na primeira ocorrência, substituímos pelo par de links. Nas próximas, apenas por um link simples.
                if "Link para PC:" not in modified_text:
                    replacement = f"🥇 Link com moedas (App):\n🔗 {link_app}\n\n🖥 Link para PC:\n🔗 {link_pc}"
                else:
                    replacement = link_app
            else:
                replacement = converted
            
            modified_text = modified_text.replace(link, replacement)
            converted_any = True

    if not converted_any:
        return False

    # Adiciona as instruções do AliExpress apenas uma vez no final se houver links dele
    if has_aliexpress:
        modified_text += (
            f"\n\n💡 Dica: Comprando pelo aplicativo o desconto pode ser maior por causa das moedas.\n"
            f"Após clicar no link acima, você será direcionado para a página de moedas. Clique no primeiro anúncio.\n"
            f"Se o produto não aparecer, clique em 'DO BRASIL'."
        )

    group_id = settings.TELEGRAM_GROUP_ID
    if not group_id:
        print("Erro: TELEGRAM_GROUP_ID não configurado.")
        return False

    try:
        final_image_to_send = None
        promo_image = None  # Imagem final (path local ou URL) para salvar no site

        if photo:
            # Se 'photo' for um caminho de arquivo (baixado pelo monitor_offers.py)
            # O bot do Telegram envia o arquivo local
            await bot.send_photo(
                chat_id=group_id,
                photo=photo,
                caption=modified_text[:1024]
            )
            final_image_to_send = photo  # Guarda o caminho do arquivo para o WhatsApp

            # Se for um file_id do Telegram (não é path e não é URL), baixa para o disco
            if isinstance(photo, str) and not photo.startswith('http') and not os.path.exists(photo):
                try:
                    tg_file = await bot.get_file(photo)
                    temp_dir = os.path.join(os.getcwd(), 'tmp_photos')
                    os.makedirs(temp_dir, exist_ok=True)
                    promo_image = await tg_file.download_to_drive(custom_path=os.path.join(temp_dir, f"promo_{int(time.time())}.jpg"))
                except Exception as dl_err:
                    print(f"Erro ao baixar foto para o site: {dl_err}")
                    promo_image = None
            else:
                promo_image = final_image_to_send
        else:
            # Tenta buscar info do produto se não tiver foto direto do Telegram
            _, image_url, _ = get_product_info(original_link)
            final_image_to_send = image_url
            promo_image = image_url
            if image_url:
                await bot.send_photo(
                    chat_id=group_id,
                    photo=image_url,
                    caption=modified_text[:1024]
                )
            else:
                await bot.send_message(
                    chat_id=group_id,
                    text=modified_text,
                    disable_web_page_preview=False
                )
        
        # Envia também para o WhatsApp (Passando o arquivo local ou a URL)
        send_whatsapp_message(modified_text, final_image_to_send)

        # Salva a promoção no banco para a página web
        save_promo_to_db(modified_text, promo_image)
        
        return True
    except Exception as e:
        print(f"Erro ao processar oferta automática: {e}")
        return False
