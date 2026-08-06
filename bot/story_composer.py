import os
import logging
from PIL import Image, ImageDraw, ImageFont, ImageOps
from django.conf import settings

logger = logging.getLogger(__name__)

# Áreas do template (1080x1920), medidas a partir da análise dos pixels
AREA_IMAGEM = (21, 400, 1058, 1220)
AREA_TITULO = (205, 1221, 971, 1489)
AREA_VALOR = (153, 1490, 721, 1671)

FONTE_DIR = os.path.join(os.path.dirname(__file__), 'static', 'bot', 'fonts')


def _carregar_fonte(tamanho, bold=False):
    """Carrega a fonte Inter (variável) e aplica peso Bold quando solicitado."""
    caminho = os.path.join(FONTE_DIR, 'Inter.ttf')
    if not os.path.exists(caminho):
        return None
    try:
        fonte = ImageFont.truetype(caminho, tamanho)
        if bold:
            try:
                fonte.set_variation_by_name('Bold')
            except Exception:
                pass
        return fonte
    except Exception as e:
        logger.warning(f"Fonte Inter não carregada: {e}")
        return None


def _ajustar_texto(draw, texto, area, fonte, cor, alinhar_centro=False):
    """Desenha o texto ajustado (com quebra de linha) dentro da área."""
    x0, y0, x1, y1 = area
    largura_max = x1 - x0
    altura_max = y1 - y0

    linhas = []
    for palavra in (texto or '').split(' '):
        if not linhas:
            linhas.append(palavra)
            continue
        teste = linhas[-1] + ' ' + palavra
        if draw.textlength(teste, font=fonte) <= largura_max:
            linhas[-1] = teste
        else:
            linhas.append(palavra)

    if not linhas:
        return

    altura_linha = fonte.size * 1.25
    total = len(linhas) * altura_linha
    y_atual = y0 + max(0, (altura_max - total) / 2)

    for linha in linhas:
        if alinhar_centro:
            larg = draw.textlength(linha, font=fonte)
            x = x0 + max(0, (largura_max - larg) / 2)
        else:
            x = x0
        draw.text((x, y_atual), linha, font=fonte, fill=cor)
        y_atual += altura_linha


def _desenhar_texto_multilinha(draw, texto, area, fonte, cor, altura_linha=None):
    """Desenha texto respeitando as quebras de linha ('\n') do texto original,
    com quebra por largura quando uma linha é longa demais."""
    from PIL import ImageFont
    x0, y0, x1, y1 = area
    largura_max = x1 - x0
    altura_max = y1 - y0
    if altura_linha is None:
        altura_linha = int(fonte.size * 1.3)

    linhas_finais = []
    for bloco in (texto or '').replace('\r', '').split('\n'):
        palavras = bloco.split(' ')
        linhas = ['']
        for palavra in palavras:
            teste = linhas[-1] + (' ' if linhas[-1] else '') + palavra
            if draw.textlength(teste, font=fonte) <= largura_max:
                linhas[-1] = teste
            else:
                linhas.append(palavra)
        linhas_finais.extend(linhas or [''])

    y = y0
    for linha in linhas_finais:
        if y + altura_linha > y1:
            break
        draw.text((x0, y), linha, font=fonte, fill=cor)
        y += altura_linha


def compor_story_card(foto_path, mensagem, output_path=None):
    """
    Compõe o Story no estilo 'card do site' (1080x1920):
      - Foto do produto no topo (crop para preencher)
      - Texto completo da promoção logo abaixo (como no card)
      - Faixa 'LINK NA BIO' no rodapé
    Retorna o caminho da imagem gerada.
    """
    W, H = 1080, 1920
    base = Image.new('RGB', (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(base)

    # faixa superior de marca/loja
    draw.rectangle([(0, 0), (W, 110)], fill=(20, 24, 38))
    fonte_marca = _carregar_fonte(48, bold=True)
    if fonte_marca:
        draw.text((40, 28), 'NITRO TECH', font=fonte_marca, fill=(255, 255, 0))

    # foto do produto
    AREA_FOTO = (40, 140, W - 40, 860)
    if foto_path and os.path.exists(foto_path):
        try:
            foto = Image.open(foto_path).convert('RGB')
            box_larg = AREA_FOTO[2] - AREA_FOTO[0]
            box_alt = AREA_FOTO[3] - AREA_FOTO[1]
            foto = ImageOps.fit(foto, (box_larg, box_alt), method=Image.LANCZOS)
            base.paste(foto, (AREA_FOTO[0], AREA_FOTO[1]))
        except Exception as e:
            logger.warning(f"Foto não colada: {e}")

    # texto completo da promo
    fonte_texto = _carregar_fonte(46)
    if fonte_texto and mensagem:
        _desenhar_texto_multilinha(draw, mensagem, (60, 890, W - 60, 1600), fonte_texto, (40, 40, 40))

    # "LINK NA BIO" no rodapé da área branca (final do card), sem barra externa
    fonte_bio = _carregar_fonte(58, bold=True)
    if fonte_bio:
        marcador = '🔗  LINK NA BIO'
        larg = draw.textlength(marcador, font=fonte_bio)
        x = (W - larg) / 2
        # selo discreto: fundo escuro arredondado só em volta do texto
        from PIL import ImageDraw as _ID
        pad_x, pad_y = 30, 18
        y = 1660
        draw.rounded_rectangle(
            [(x - pad_x, y - pad_y), (x + larg + pad_x, y + fonte_bio.size + pad_y)],
            radius=20, fill=(20, 24, 38)
        )
        draw.text((x, y), marcador, font=fonte_bio, fill=(255, 255, 0))

    if not output_path:
        output_path = os.path.join(settings.MEDIA_ROOT, 'promos', f'story_{int(__import__("time").time())}.jpg')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    base.save(output_path, 'JPEG', quality=92)
    return output_path


def compor_story(foto_path, titulo, valor, output_path=None):
    """
    Compõe a imagem do Story a partir do template do usuário.
    - Foto do produto na área branca (com crop para preencher)
    - Título do produto na área cinza
    - Valor na área marrom
    Retorna o caminho da imagem gerada.
    """
    template = os.path.join(
        os.path.dirname(__file__), 'static', 'bot', 'stories', 'Cópia de Modelo_Stories_Padrao.png'
    )
    if not os.path.exists(template):
        template = os.path.join(settings.MEDIA_ROOT, 'stories', 'Cópia de Modelo_Stories_Padrao.png')
    if not os.path.exists(template):
        logger.warning(f"Template de Story não encontrado: {template}")
        return None

    base = Image.open(template).convert('RGB')
    draw = ImageDraw.Draw(base)

    # 1. Foto do produto na área branca (crop para preencher)
    if foto_path and os.path.exists(foto_path):
        try:
            foto = Image.open(foto_path).convert('RGB')
            box = AREA_IMAGEM
            box_larg = box[2] - box[0]
            box_alt = box[3] - box[1]
            foto = ImageOps.fit(foto, (box_larg, box_alt), method=Image.LANCZOS)
            base.paste(foto, (box[0], box[1]))
        except Exception as e:
            logger.warning(f"Foto do produto não colada: {e}")

    # 2. Título na área cinza
    fonte_titulo = _carregar_fonte(62, bold=True)
    if fonte_titulo and titulo:
        titulo = (titulo[:47] + '...') if len(titulo) > 50 else titulo
        _ajustar_texto(draw, titulo, AREA_TITULO, fonte_titulo, (40, 40, 40))

    # 3. Valor na área marrom
    fonte_valor = _carregar_fonte(86, bold=True)
    if fonte_valor and valor:
        _ajustar_texto(draw, valor, AREA_VALOR, fonte_valor, (255, 255, 255), alinhar_centro=True)

    if not output_path:
        output_path = os.path.join(settings.MEDIA_ROOT, 'promos', f'story_{int(__import__("time").time())}.jpg')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    base.save(output_path, 'JPEG', quality=92)
    return output_path
