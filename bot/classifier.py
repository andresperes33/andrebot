import re
import unicodedata


def sem_acento(texto):
    return unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode('ascii')


def _norm(texto):
    return re.sub(r'\s+', ' ', sem_acento(texto or '')).lower()


def _limpar_compat(texto):
    """Remove cláusulas de compatibilidade ('compatível com laptop') que não
    indicam o produto em si. Ex.: 'Crucial SSD ... compatível com laptop'
    continua sendo um SSD, não um notebook."""
    if not texto:
        return texto
    # Normaliza para o regex (evita 'compatível' com acento não casar).
    base = sem_acento(texto or '')
    # Apaga desde 'compatível' até o fim da cláusula (vírgula, ponto ou fim).
    return re.sub(r'\s+compativel\s*(com\b|para\b|:|\s)*[^,;.]*', ' ', base, flags=re.I)


# Padrões por categoria, em ordem de prioridade (mais específica primeiro).
# Todos os padrões são aplicados sobre texto normalizado (sem acento, minúsculo).
# Obs.: 'kit' não entra aqui — é tratado antes, com validação de hardware
# (só é kit se vier placa-mãe/processador/memória junto), ver detectar_categoria.
_REGEX_CATEGORIA = [
    ('console', [
        r'\bnintendo\b', r'\bswitch\b', r'\bps[0-9]?\b', r'\bplaystation\b',
        r'\bxbox\b', r'\bsteam\s*deck\b', r'\bok\s*1\b', r'\banbernic\b',
        r'\bsup\b', r'\bhandheld\b', r'\bconsole\b',
    ]),
    ('notebook', [
        r'\bnotebook\b', r'\blaptop\b', r'\bmacbook\b', r'\bultrabook\b', r'\bchromebook\b',
    ]),
    ('celular', [
        r'\bcelular\b', r'\bsmartphone\b', r'\biphone\b', r'\bgalaxy\b',
        r'\bxiaomi\b', r'\bpoco\b', r'\bredmi\b', r'\brealme\b', r'\boneplus\b',
        r'\bzenfone\b', r'moto\s*g\d', r'samsung\s*s\d\d',
    ]),
    ('tv', [
        r'televis', r'\bsmart\s*tv\b', r'\btv\s*\d{2}\s*(pol|polegada)', r'\btv\s*\d{2}\b',
        r'\bqled\b', r'\bminiled\b', r'\boled\b',
    ]),
    ('placa_video', [
        r'placa\s*de\s*video', r'\bgpu\b', r'\bgeforce\b', r'\bradeon\b',
        r'\b(rtx|gtx)\s?\d{3,4}\b', r'\brx\s?\d{3,4}\b', r'\brx\s?\d{2,3}\b',
    ]),
    ('placa_mae', [
        r'placa[- ]mae', r'\bmotherboard\b',
        r'\b(a520|a620|b450|b550|b650|b660|b760|x570|x670|z690|z790|h610|h770)\b',
        r'\bam[45]\b', r'socket\s*am\d',
    ]),
    ('processador', [
        r'\bprocessador\b', r'\bryzen\b', r'\bintel\s*core\b', r'\bcore\s*i[3579]\b',
        r'\bi[3579]-\d{4}\b', r'\bathlon\b', r'\bthreadripper\b', r'\bxeon\b',
    ]),
    ('memoria_ram', [
        r'\bddr[345]\b', r'memoria\s*ram', r'\bram\s*\d+', r'\bxmp\b',
    ]),
    ('ssd', [
        r'\bssd\b', r'\bnvme\b', r'\bm\.2\b', r'\bhdd\b', r'\bhard\s*disk\b',
        r'\barmazenamento\b', r'\bsata\b',
    ]),
    ('monitor', [
        r'\bmonitor\b', r'\bdisplay\b', r'\bultrawide\b', r'\bcurvo\b', r'\bpainel\b',
        r'\b(144|165|240|280|360)hz\b', r'\b1440p\b',
    ]),
    ('headset', [
        r'\bheadset\b', r'\bheadphone\b', r'\bfone\b', r'\bfone\s*de\s*ouvido\b',
        r'\bauricular\b', r'\bearbuds?\b',
    ]),
    ('teclado', [
        r'\bteclado\b', r'\bkeyboard\b', r'\bteclado\s*mecanico\b', r'\bswitch\s*(red|blue|brown|mechanical)\b',
    ]),
    ('mousepad', [
        r'\bmouse ?pad\b', r'\bmousepad\b', r'\bpad\b', r'\bpisapads?\b', r'\bcontrol\s*pad\b',
    ]),
    ('mouse', [
        r'\bmouse\b',
    ]),
    ('fonte', [
        r'\bpsu\b', r'\batx\b', r'\b\d{3,4}\s*w\b', r'\bfonte\s*(atx)?\s*\d{3,4}\s*w\b',
    ]),
    ('gabinete', [
        r'\bgabinete\b', r'\bcomputer\s*case\b', r'\bmid\s*tower\b', r'\btorre\b', r'\bchassi\b',
    ]),
    ('cooler', [
        r'\bcooler\b', r'\bwater\s*cooler\b', r'\bwatercooler\b', r'\bdissipador\b',
        r'\bventoinha\b', r'\baio\b',
    ]),
    ('controle', [
        r'\bgamepad\b', r'\bjoystick\b', r'\bjoypad\b', r'\bdualsense\b', r'\bcontrole\b',
    ]),
    ('webcam', [
        r'\bwebcam\b', r'\bweb\s*cam\b', r'\bvideocam\b',
    ]),
    ('roteador', [
        r'\broteador\b', r'\brouter\b', r'\bwifi\s*6e?\b', r'\bmesh\b',
    ]),
    ('cadeira', [
        r'\bcadeira\b', r'\bgamer\s*chair\b', r'\bchair\b',
    ]),
    ('impressora', [
        r'\bimpressora\b', r'\bprinter\b', r'\bmultifuncional\b', r'\btoner\b',
    ]),
]


def detectar_categoria(texto, titulo=None):
    """Classifica um texto de promoção em uma das categorias do site.
    Se 'titulo' (linha do produto) for informado, usa-o com prioridade,
    pois o assunto principal é o que nomeia o produto (ex.: 'Processador
    ... Radeon ...' é processador, não placa de vídeo)."""
    haystack = _norm(texto)
    if not haystack:
        return 'outros'

    # Remove cláusulas de compatibilidade do texto completo, assim
    # 'compatível com laptop/notebook' não é confundido com o produto.
    haystack = _norm(_limpar_compat(texto))

    # Postagem só de cupom: o título é um anúncio curto com 'cupom'
    # (ex.: 'Novo Cupom AMAZON'). Nesse caso o produto não existe.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        primeira_linha = _norm(alvo.split('\n')[0])
        if not primeira_linha:
            continue
        if re.search(r'(?<!\w)cupom(?!\w)', primeira_linha) and len(primeira_linha) <= 45:
            return 'cupom'

    # Kit (placa-mãe + processador + memória) tem prioridade sobre qualquer
    # componente individual: 'Processador Kit X99 ...' é um kit, não um
    # processador. Só considera kit quando há hardware de PC junto, para
    # não pegar 'kit de limpeza', 'kit de 2 peças', etc.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        limpo = _norm(_limpar_compat(alvo))
        if not limpo:
            continue
        tem_kit = re.search(r'\bkit\b', limpo)
        tem_hardware = re.search(
            r'\b(x99|x79|xeon|processador|placa[ -]?mae|memoria|ddr|c612|s2011|core\s*i[3579]|ryzen|am[45]|motherboard|gabinete|fonte|fan|ventoinha|cooler)\b',
            limpo,
        )
        if tem_kit and tem_hardware:
            return 'kit'

    # Se houver título do produto, busca nele primeiro. A primeira palavra
    # tem prioridade (ex.: 'Processador ... Radeon' é processador). Se a
    # primeira palavra não casar, busca em todo o título (ex.: 'Crucial SSD',
    # onde 'Crucial' é só a marca e 'SSD' identifica o produto).
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        limpo = _norm(_limpar_compat(alvo))
        if not limpo:
            continue
        primeira = limpo.split('\n')[0]
        for categoria, padroes in _REGEX_CATEGORIA:
            for p in padroes:
                if re.match(p, primeira):
                    return categoria
        for categoria, padroes in _REGEX_CATEGORIA:
            for p in padroes:
                if re.search(p, limpo):
                    return categoria

    return 'outros'


# Domínio (ou parte dele) → nome de loja exibido no card.
_LOJA_POR_DOMINIO = [
    ('shopee', 'Shopee'),
    ('amazon', 'Amazon'),
    ('aliexpress', 'AliExpress'),
    ('mercadolivre', 'Mercado Livre'),
    ('mercado', 'Mercado Livre'),
    ('magazineluiza', 'Magazine Luíza'),
    ('magalu', 'Magazine Luíza'),
    ('kabum', 'KaBuM'),
    ('pichau', 'Pichau'),
    ('terabyte', 'Terabyte'),
    ('americanas', 'Americanas'),
    ('casasbahia', 'Casas Bahia'),
    ('pontofrio', 'Ponto'),
    ('submarino', 'Submarino'),
    ('walmart', 'Walmart'),
    ('renner', 'Renner'),
    ('extra.com', 'Extra'),
    ('fastshop', 'Fast Shop'),
]


def detectar_loja(link):
    """Detecta a loja a partir do domínio do link de afiliado/produto.
    Ex.: 'https://s.shopee.com.br/xyz' → 'Shopee'."""
    if not link:
        return ''
    baixo = sem_acento(link).lower()
    for chave, nome in _LOJA_POR_DOMINIO:
        if chave in baixo:
            return nome
    return ''
