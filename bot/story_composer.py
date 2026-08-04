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


def compor_story(foto_path, titulo, valor, output_path=None):
    """
    Compõe a imagem do Story a partir do template do usuário.
    - Foto do produto na área branca (com crop para preencher)
    - Título do produto na área cinza
    - Valor na área marrom
    Retorna o caminho da imagem gerada.
    """
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
