import re
import unicodedata


def sem_acento(texto):
    return unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode('ascii')


# Remove emojis, pictogramas, símbolos e caracteres invisíveis/unicode não-ASCII.
# Esses caracteres atrapalham regex como '^cupom'/'^novo cupom' e não ajudam a
# identificar o produto. Mantém letras, números, acentos (via sem_acento) e
# pontuação básica.
_RE_EMOJI = re.compile(
    r'[\U0001F000-\U0001FAFF]'      # Emojis e pictogramas
    r'|[\u2600-\u27BF]'             # Símbolos diversos (⭐, ★, ♥, etc.)
    r'|[\u2190-\u21FF]'             # Setas (⬇, ➡)
    r'|[\u2B00-\u2BFF]'             # Símbolos/moeda (💰, ⁉)
    r'|\u00a9|\u00ae|\u2122|\u00a0',  # ©, ®, ™, espaço inseparável
)


def sem_simbolo(texto):
    """Remove emojis/símbolos e colapsa espaços, preservando o texto útil."""
    t = _RE_EMOJI.sub(' ', texto or '')
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def _norm(texto):
    base = sem_acento(texto or '')
    base = _RE_EMOJI.sub(' ', base)
    return re.sub(r'\s+', ' ', base).lower().strip()


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
    ('jogo', [
        r'\bgta\b', r'\bgrand\s*theft\s*auto\b',
        r'\bmídia\s*f[ií]sica\b', r'\bmidia\s*fisica\b', r'\bblu-?ray\b',
        r'\bcodigo\b.{0,12}gta\b',
        r'\bforza\b', r'\bgod\s*of\s*war\b', r'\bzelda\b', r'\bmario\b',
        r'\bred\s*dead\b', r'\bdragon\s*ball\b', r'\bfifa\b', r'\bea\s*sports\b',
        r'\bcall\s*of\s*duty\b', r'\belden\s*ring\b', r'\bcyberpunk\b',
        # Jogo claro de produto: 'Jogo X' no início da linha OU 'jogo' como
        # rótulo do item (ex.: 'Jogo PS5 GTA'). Evita pegar 'Hifi para Jogos'.
        r'\bjogo\s+(?:de|do|da|d[aeo]?\s+)?[a-z0-9]',
        r'\bcopy\s*de\s*(?:cart\b|catridge)',
    ]),
    ('console', [
        # 'switch' só é console (Nintendo Switch) — não é switch mecânico de teclado.
        r'\bswitch\b(?=\s*(?:nintendo|oled|lite|2\b|\d|joy|v2))|(?<=\bnintendo\s)switch',
        r'\bplaystation\b(?![^.\n]*(?:para|compat[ií]vel|compativel|computador|pc\b|fone|headset|controle|acess[oó]rio))',
        r'\bnintendo\b(?!\s*(?:switch\s+(?:lite|oled)))(?![^.,\n]*(?:para\b|fone|controle|acess[oó]rio))',
        r'\bxbox\b(?![^.,\n]*(?:para\b|fone|controle|headset|acess[oó]rio|series\s*[sx]\s*compat))',
        r'\bsteam\s*deck\b', r'\bok\s*1\b', r'\banbernic\b',
        r'\bsup\b', r'\bhandheld\b', r'\bconsole\b',
        # 'ps5'/'ps4' sozinho (ex.: 'PS5 Slim') só é console se NÃO estiver
        # numa lista de compatibilidade ('para ps5', 'ps5, ps4', 'ps5 pc').
        r'\bps[0-9]\b(?!ps[0-9]|,[^.\n]*ps[0-9]|[^.\n]*\b(?:para|compat[ií]vel|compativel|computador|fone|headset|controle|ssd|disco|jogo|acess[oó]rio)\b)',
    ]),
    ('notebook', [
        # Só é notebook quando é o PRODUTO, não compatibilidade
        # ('para PC e Notebook', 'compatível com notebook', 'pc e notebook').
        r'\bnotebook\b(?<!para )(?<!pc e )(?<!com )(?<!e )',
        r'\blaptop\b(?<!para )(?<!pc e )(?<!com )(?<!e )',
        r'\bmacbook\b', r'\bultrabook\b', r'\bchromebook\b',
        r'\bgalaxy\s*book\s*\w*', r'\bwindows\s*11\b', r'\bwindows\s*10\b',
        r'\btela\s*(?:ips|amoled|de\s*\d+[\.,]?\d*\s*"|de\s*\d+\s*polegadas)',
        r'\bintel\s*core\s*ultra\b', r'\bi3-?1\d{4}\b', r'\bi5-?1\d{4}\b', r'\bi7-?1\d{4}\b',
    ]),
    ('celular', [
        r'\bcelular\b', r'\bsmartphone\b', r'\biphone\b',
        r'\bxiaomi\b', r'\bpoco\b', r'\bredmi\b', r'\brealme\b', r'\boneplus\b',
        r'\bzenfone\b', r'moto\s*g\d', r'samsung\s*s\d\d', r'\binfinix\b', r'\bpositivo\b',
        r'\bmotorola\b', r'\bmoto\s*edges?\b', r'\bedge\s*\d{2}\s*(?:fusion|ultra|pro|neo)\b', r'\bmoto\b',
        # 'galaxy' virou celular, mas pega a linha de fans 'Jungle Leopard
        # Galaxy' e notebooks 'Samsung Galaxy Book'. Só é celular se for
        # Samsung Galaxy (celular) ou sem contexto de fan/notebook.
        r'\bgalaxy\b(?!\s*(?:v\d|magn|argb|\d+mm|book|chrome))',
        r'\bsamsung\s*galaxy\b(?!\s*book)', r'galaxy\s+[as]\s?\d',
    ]),
    ('tv', [
        r'televis', r'\bsmart\s*tv\b', r'\btv\s*\d{2}\s*(pol|polegada)', r'\btv\s*\d{2}\b',
        r'\bqled\b', r'\bminiled\b', r'\boled\b',
    ]),
    ('pasta_termica', [
        r'pasta\s*t[eé]rmica', r'\bpasta\b.*\bt[eé]rmic', r'\bcomposto\s*de\s*silicone\b',
        r'\bthermal\s*compound\b', r'\bthermal\s*paste\b', r'\btermal\b',
    ]),
    ('placa_video', [
        r'placa\s*de\s*video', r'\bgpu\b', r'\bgeforce\b', r'\bradeon\b',
        r'\b(rtx|gtx)\s?\d{3,4}\b', r'\brx\s?\d{3,4}\b', r'\brx\s?\d{2,3}\b',
    ]),
    ('placa_mae', [
        r'placa[- ]mae', r'\bmotherboard\b',
        r'\b(a520|a620|b450|b550|b650|b660|b760|x570|x670|z690|z790|h610|h770)\b',
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
    ('caixa_som', [
        r'caixa\s*de\s*som', r'\bsoundbar\b', r'\bcaixa\s*som\b',
        r'\bcx\s*\d{3,4}\b', r'\bbritania\b',
    ]),
    ('fonte', [
        r'\bpsu\b', r'\batx\b', r'\b\d{3,4}\s*w\b', r'\bfonte\s*(atx)?\s*\d{3,4}\s*w\b',
    ]),
    ('gabinete', [
        r'\bgabinete\b', r'\bcomputer\s*case\b', r'\bmid\s*tower\b', r'\btorre\b', r'\bchassi\b',
    ]),
    ('cooler', [
        r'\bcooler\b', r'\bwater\s*cooler\b', r'\bwatercooler\b', r'\bdissipador\b',
        r'\bventoinhas?\b', r'\baio\b', r'\bfan(s)?\b', r'\bfans?\s*magn[eé]tic',
        r'\bargb\b', r'kit\s*\d+\s*fans?', r'kit\s+ventoinhas?',
    ]),
    ('controle', [
        r'\bgamepad\b', r'\bjoystick\b', r'\bjoypad\b', r'\bdualsense\b', r'\bcontrole\b',
    ]),
    ('microfone', [
        r'\bmicrofone\b', r'\bmicrophone\b', r'\bmic\b', r'\bmic\s*din[aâ]mic',
        r'\bxlr\b', r'\bpodcast\s*mic', r'\bcondensador\b',
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

    # Cooler/air cooler/water cooler tem prioridade — 'torre' do cooler
    # (torre de dissipação) não deve virar gabinete.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:air\s*cooler|water\s*cooler|watercooler|dissipador|cooler\b.*torre|torre\b.*cooler|ventoinha)\b', alvo_norm):
            return 'cooler'

    # Placa-mãe explícita tem prioridade sobre qualquer processador/notebook
    # citado ('MSI Placa-mãe PRO ... suporta Intel Core Ultra' é uma PLACA-MÃE).
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:placa[ -]?mae|motherboard|mainboard)\b', alvo_norm):
            return 'placa_mae'

    # Produtos de áudio/acessórios têm prioridade sobre "notebook" quando a
    # palavra 'notebook' é só compatibilidade ('caixa de som para notebook').
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:caixa\s*de\s*som|soundbar|caixa\s*som|microfone|headset|fone\s*de\s*ouvido)\b', alvo_norm) and \
           re.search(r'\b(?:pc|notebook|laptop)\b', alvo_norm):
            # É um produto de áudio, e 'notebook' aparece só como compatibilidade
            if re.search(r'caixa\s*de\s*som|soundbar|caixa\s*som', alvo_norm):
                return 'caixa_som'
            if re.search(r'\bmicrofone\b', alvo_norm):
                return 'microfone'
            if re.search(r'\b(?:headset|fone\s*de\s*ouvido)\b', alvo_norm):
                return 'headset'

    # Notebook tem prioridade sobre qualquer GPU citada no título (ex.:
    # 'RTX 5050 Notebook Asus TUF' é um NOTEBOOK, não uma placa de vídeo).
    # Mas "notebook" como COMPATIBILIDADE ('para PC e Notebook', 'compatível
    # com notebook') NÃO torna o produto um notebook (ex.: caixa de som).
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:para|compat[ií]vel|com|pc\s*e|pc\b|no\s*pc)\s*(?:pc\s*e\s*)?(?:notebook|laptop)\b', alvo_norm):
            continue  # é compatibilidade, não anúncio de notebook
        if re.search(r'\b(?:notebook|laptop|macbook|ultrabook|chromebook|galaxy\s*book)\b', alvo_norm):
            return 'notebook'

    # Bundle de CONSOLE tem prioridade sobre jogos: 'PlayStation 5 + GTA VI'
    # é um console com jogos inclusos (bundle/pacote), não um jogo avulso.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        eh_console = re.search(
            r'(?:playstation\s?[1-5]?|ps\s?[1-5]|xbox|nintendo\s*switch|switch)',
            alvo_norm,
        )
        eh_bundle = re.search(r'\b(?:bundle|pacote|com\s*jogos|jogo\s*incluso|edicao\s*com)\b', alvo_norm)
        if eh_console and eh_bundle:
            return 'console'

    # Postagem só de cupom: o título é um anúncio curto com 'cupom'
    # (ex.: 'Novo Cupom AMAZON', 'Novos Cupons Shopee LIVE').
    # Se a PRIMEIRA linha é claramente um anúncio de cupom, é cupom direto —
    # mesmo que o resto do texto (normalizado) pareça ter produto.
    from bot.services import _eh_anuncio_cupom, _eh_linha_titulo_produto
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        primeira_linha = _norm(alvo.split('\n')[0])
        if not primeira_linha:
            continue
        if _eh_anuncio_cupom(primeira_linha):
            return 'cupom'

    # Senão, verifica se há um produto real no texto (ex.: 'Water Cooler ...
    # cupom GAMER10' é um produto com cupom, não um cupom).
    tem_produto_real = False
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        for linha in _norm(alvo).split('\n'):
            if _eh_linha_titulo_produto(linha):
                tem_produto_real = True
                break
        if tem_produto_real:
            break
    if tem_produto_real:
        # Não é cupom puro — segue para a classificação normal de produto.
        pass

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
            r'\b(x99|x79|xeon|processador|placa[ -]?mae|memoria|ddr|c612|s2011|core\s*i[3579]|ryzen|am[45]|motherboard|gabinete|fonte)\b',
            limpo,
        )
        if tem_kit and tem_hardware:
            return 'kit'

    # Cupom genérico SEM a palavra 'cupom' no título (ex.: 'AUMENTOU O
    # LIMITE!!', '10% OFF', 'Limite de R$ 200,00 OFF', 'Compra mínima').
    # Só é cupom se o título NÃO for nome de produto (nenhuma categoria
    # casa), senão 'Notebook 10% OFF' viraria cupom.
    alvo_titulo = titulo or texto
    if alvo_titulo:
        t_limpo = _norm(_limpar_compat(alvo_titulo))
        # Verifica se o texto (não só a primeira linha) é um produto real.
        # Assim 'Positivo Infinix ... 15% OFF' não vira cupom.
        eh_produto = any(
            re.search(p, t_limpo)
            for _, padroes in _REGEX_CATEGORIA
            for p in padroes
        )
        if not eh_produto:
            texto_baixo = _norm(texto)
            tem_off = re.search(r'\b\d+\s*%?\s*(?:off|de desconto)\b', texto_baixo)
            tem_limite = re.search(r'\b(?:limite|compra\s*m[ií]nima)\b', texto_baixo)
            tem_cupom = 'cupom' in texto_baixo or 'cupons' in texto_baixo or 'desconto' in texto_baixo
            if tem_off and (tem_limite or tem_cupom):
                return 'cupom'

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
