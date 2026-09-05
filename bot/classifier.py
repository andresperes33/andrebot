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
    # Remove URLs (o slug do link pode conter nome de outro produto, ex.:
    # link de cupom apontando para 'monitor-gamer-aoc...' — não deve
    # influenciar a categoria do anúncio).
    base = re.sub(r'https?://[^\s<>"\']+', ' ', base, flags=re.I)
    # Apaga desde 'compatível' até o fim da cláusula (vírgula, ponto ou fim).
    base = re.sub(r'\s+compativel\s*(com\b|para\b|:|\s)*[^,;.]*', ' ', base, flags=re.I)
    # Apaga 'para <aparelho>' quando o aparelho citado é só compatibilidade
    # (ex.: 'Carregador ... para macbook, tablet, iphone, notebook' é um
    # carregador, não um notebook/tablet). Preserva 'para' de produtos reais.
    base = re.sub(
        r'\s+para\s+(?:o\s+|a\s+)?(?:macbook|notebook|laptop|tablet|tablete|ipad|'
        r'iphone|telefone|celular|smartphone|pc\b|windows|android|ios|computador)\b[^,;.]*',
        ' ',
        base,
        flags=re.I,
    )
    return base


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
    ('ar_condicionado', [
        r'\bar\s*condicionado\b', r'\bcondicionador\b', r'\bair\s*conditioner\b',
        r'\barcel\b', r'\bsplit\s*hi\s*wall\b', r'\bhi\s*wall\b',
        r'\b12\.000\s*btus\b', r'\b9\.000\s*btus\b', r'\b18\.000\s*btus\b',
        r'\b24\.000\s*btus\b', r'\binverter\b(?=.*\b(?:\btu|frio|quente|condicionado|ar\b|wall)\b)',
    ]),
    ('cabo', [
        r'\busb\s*cabe\b', r'\bcable\b',
        r'\bcarregador\b', r'\badaptador\s*de\s*energia\b', r'\bpd\s*60w\b',
        r'\busb\s*c\b.*\bcabo\b', r'\btipo[- ]c?\s*cabo\b',
        r'\bhdmi\b.*\bcabo\b', r'\bcabo\b.*\bhdmi\b',
        r'\bcabo\b.*\busb\b', r'\busb\b.*\bcabo\b',
        r'\bcabo\b.*(?:energia|carregador|alimenta)',
    ]),
    ('notebook', [
        # Só é notebook quando é o PRODUTO, não compatibilidade
        # ('para PC e Notebook', 'compatível com notebook', 'pc e notebook').
        # Obs.: lookbehind negativo precisa vir ANTES da palavra (depois não
        # funciona e 'para notebook' viraria notebook erroneamente).
        r'(?<!para )(?<!pc e )(?<!com )(?<!e )\bnotebook\b',
        r'(?<!para )(?<!pc e )(?<!com )(?<!e )\blaptop\b',
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
        r'\bgalaxy\b(?!\s*(?:v\d|magn|argb|\d+mm|book|chrome|tab))',
        r'\bsamsung\s*galaxy\b(?!\s*book)', r'galaxy\s+[as]\s?\d',
    ]),
    ('tv', [
        r'televis', r'\bsmart\s*tv\b', r'\btv\s*\d{2}\s*(pol|polegada)', r'\btv\s*\d{2}\b',
        r'\btv\b.{0,40}?\b\d{2}\s*(?:pol|polegadas|polegada)',
        r'\btv\b(?!\s*box).{0,40}?\b\d{2}\b',
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
        r'\bmonitor\b', r'\bdisplay\b', r'\bultrawide\b', r'\bcurvo\b',
        # 'painel' de monitor (painel IPS/VA/TN), mas NÃO 'painel solar' de
        # câmera de segurança (ex.: 'Câmera Baseus ... painel solar 2K').
        r'\bpainel\b(?!\s*solar)', r'\bpainel\s*(?:ips|va|tn|led|amoled|curvo|ultrawide)\b',
        r'\b(144|165|240|280|360)hz\b', r'\b1440p\b',
    ]),
    ('headset', [
        r'\bheadset\b', r'\bheadphone\b', r'\bfone\b', r'\bfones\b',
        r'\bfone\s*de\s*ouvido\b', r'\bfones\s*de\s*ouvido\b',
        r'\bauricular\b', r'\bearbuds?\b', r'\btws\b', r'\bin[- ]ear\b',
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
        r'caixa\s*de\s*som', r'caixinha\s*de\s*som', r'\bsoundbar\b', r'\bcaixa\s*som\b',
        r'\balto[- ]falante\b', r'\baltofalante\b', r'\bspeaker\b', r'\bmini\s*caixa\b',
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

    # Detecta se o texto tem um PRODUTO real (ex.: 'Water Cooler').
    # Se tiver, um 'Cupom: X' presente é só cupom do produto → não é cupom puro.
    from bot.services import _eh_anuncio_cupom, _eh_linha_titulo_produto
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

    # Postagem só de cupom: QUALQUER linha que seja claramente um anúncio
    # curto de cupom (ex.: 'NOVO Cupom Mercado Livre') torna o anúncio cupom.
    # Só quando NÃO há um produto real (senão 'Cooler + Cupom' viraria cupom).
    if not tem_produto_real:
        for alvo in (titulo, texto,):
            if not alvo:
                continue
            for linha in _norm(alvo).split('\n'):
                if _eh_anuncio_cupom(linha):
                    return 'cupom'

    # Tablet tem prioridade — 'Galaxy Tab S10 Lite ... Tela 10.9"' é um tablet,
    # não um celular (mesmo vindo 'Galaxy'/'Samsung').
    # Mas 'Carregador ... para macbook, tablet, telefone, iphone' é um
    # CARREGADOR; 'tablet'/'macbook'/'iphone' ali são só compatibilidade.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:carregador|cabo|adaptador|fonte)\b', alvo_norm) and \
           re.search(r'\b(?:tablet|tablete|ipad|macbook|iphone|notebook|laptop|telefone|celular)\b', alvo_norm):
            continue  # é carregador/cabo; aparelho citado é só compatibilidade
        # 'Kit Teclado e Mouse ... Tablet Celular' — o produto é um teclado
        # (com mouse); 'tablet'/'celular' é só compatibilidade, não um tablet.
        if re.search(r'\b(?:teclado|keyboard)\b', alvo_norm) and \
           re.search(r'\b(?:tablet|tablete|ipad|celular|telefone|smartphone|android|ios)\b', alvo_norm):
            return 'teclado'
        if re.search(r'\b(?:tablet|tablete)\b', alvo_norm):
            return 'tablet'
        if re.search(r'\bipad\b', alvo_norm):
            return 'tablet'
        if re.search(r'\bgalaxy\s*tab\b', alvo_norm):
            return 'tablet'
        if re.search(r'\btab\s+[sa]\s?\d', alvo_norm):
            return 'tablet'

    # Fonte tem prioridade — 'Fonte 850W ... com Cabo' é uma fonte, não um cabo.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\bfonte\b', alvo_norm) and re.search(r'\b\d{2,4}\s*w\b', alvo_norm):
            return 'fonte'
        if re.search(r'\b(?:fonte|psu)\b', alvo_norm):
            return 'fonte'

    # Controle/gamepad tem prioridade — 'Controle GameSir ... iPhone/Android'
    # é um controle para celular, não um celular. Mas se o anúncio é de uma TV
    # ('Smart TV ... Controle AI Magic'), o 'controle' é o controle remoto
    # incluso na TV, não um gamepad avulso.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:smart\s*tv|televis|tv\s*\d{2}|qled|miniled|neo\s*qled)\b', alvo_norm) and \
           re.search(r'\bcontrole\b', alvo_norm):
            continue  # é TV; 'controle' é o controle remoto incluso
        # Microfone com controle de volume RGB ('Microfone FIFINE ... Controle
        # RGB') — o 'controle' é um botão do microfone, não um gamepad avulso.
        if re.search(r'\bmicrofone\b', alvo_norm) and re.search(r'\bcontrole\b', alvo_norm):
            continue
        # Caixa de som com 'controle por aplicativo' — o 'controle' é um
        # recurso do app da caixa, não um gamepad avulso.
        if re.search(r'\b(?:caixa\s*de\s*som|caixa\s*som|soundbar|speaker|bluetooth)\b', alvo_norm) and \
           re.search(r'\bcontrole\b', alvo_norm):
            continue
        if re.search(r'\b(?:controle|gamepad|joystick|joypad|gamepad\s*controller)\b', alvo_norm):
            return 'controle'

    # Ar condicionado tem prioridade — 'Ar Condicionado Inverter Hi Wall' é um
    # ar-condicionado, não um 'inverter' genérico nem outro componente.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:ar\s*condicionado|condicionador|air\s*conditioner|split\s*hi\s*wall|hi\s*wall)\b', alvo_norm):
            return 'ar_condicionado'

    # Gabinete tem prioridade sobre 'placa-mãe' — 'Gabinete Gamer ...
    # Micro-ATX/Mid' é um GABINETE; 'micro-atx' (muitas vezes dentro da URL
    # do produto) não é uma placa-mãe.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\bgabinete\b', alvo_norm):
            return 'gabinete'

    # Notebook tem prioridade sobre GPU/SSD citados no título
    # ('RTX5060 Notebook ASUS TUF ... 512GB SSD' é um NOTEBOOK, não um SSD).
    # 'notebook' de compatibilidade ('para notebook') NÃO conta aqui.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:para|compat[ií]vel|com|no|cabo|cabos|carregador)\s*(?:pc\s*e\s*)?(?:notebook|laptop|macbook)\b', alvo_norm):
            continue
        if re.search(r'\b(?:notebook|laptop|macbook|ultrabook|chromebook)\b', alvo_norm):
            return 'notebook'

    # Kit (placa-mãe + processador + memória) tem prioridade sobre qualquer
    # componente individual: 'Kit X99 ... Xeon ... DDR3' é um kit, não um
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

    # Processador tem prioridade sobre a plataforma/placa citada
    # ('Xeon E5 ... x99 Processador CPU' é um PROCESSADOR, não uma placa-mãe).
    # Mas 'Cooler para Processador'/'Dissipador para CPU' é um COOLER, não um
    # processador — 'processador' ali é só a compatibilidade do cooler.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        eh_cooler = re.search(r'\b(?:cooler|dissipador|ventoinha|water\s*cooler|air\s*cooler|watercooler)\b', alvo_norm)
        proc_como_compat = re.search(r'\b(?:para|pra|compat[ií]vel\s*com|com)\s*(?:processador|cpu)\b', alvo_norm)
        if eh_cooler and proc_como_compat:
            return 'cooler'
        # 'Placa-mãe ... Suporta processadores Intel Core Ultra' — o
        # 'processador' é compatibilidade da placa-mãe, não um CPU avulso.
        eh_placa_mae = re.search(r'\b(?:placa[ -]?mae|motherboard|mainboard)\b', alvo_norm)
        if eh_placa_mae and re.search(r'\b(?:processador|processadores|cpu|intel\s*core|core\s*i[3579]|core\s*ultra|xeon|ryzen)\b', alvo_norm):
            return 'placa_mae'
        # 'Smart TV ... Processador AI a7 Gen8' — o 'processador' é o chip
        # embarcado da TV, não um CPU avulso.
        if re.search(r'\b(?:smart\s*tv|televis|tv\s*\d{2}|qled|oled|miniled|neo\s*qled)\b', alvo_norm):
            continue
        # 'Air Cooler AMD novo ryzen wraith' — é um air cooler; 'ryzen' é a
        # plataforma compatível do cooler, não um CPu avulso.
        eh_cooler_produto = re.search(r'\b(?:air\s*cooler|water\s*cooler|watercooler|dissipador|ventoinha|wraith|cooler)\b', alvo_norm)
        if eh_cooler_produto and re.search(r'\b(?:processador|cpu|ryzen|xeon|intel\s*core|core\s*i[3579]|athlon|threadripper)\b', alvo_norm):
            continue
        # 'Pasta Térmica ... para CPU GPU' — é pasta térmica; 'cpu'/'gpu' é
        # só a aplicação, não um processador avulso.
        eh_pasta_termica = re.search(r'\b(?:pasta\s*t[eé]rmica|pasta\b|composto\s*de\s*silicone|thermal\s*compound|thermal\s*paste|termal)\b', alvo_norm)
        if eh_pasta_termica and re.search(r'\b(?:processador|cpu|gpu|ryzen|xeon|intel\s*core)\b', alvo_norm):
            return 'pasta_termica'
        if re.search(r'\b(?:processador|cpu|xeon|ryzen|intel\s*core|core\s*i[3579]|athlon|threadripper)\b', alvo_norm):
            return 'processador'

    # Placa-mãe explícita tem prioridade sobre qualquer processador/SSD
    # citado ('Asus Prime A520M-R ... Ddr4 M.2 Chipset A520' é uma PLACA-MÃE).
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:placa[ -]?mae|motherboard|mainboard|chipset|quad\s*channel)\b', alvo_norm):
            return 'placa_mae'
        if re.search(r'\b(?:x99|x79|x58|c612|s2011|matx|atx|micro\s*atx)\b', alvo_norm):
            return 'placa_mae'
        if re.search(r'\b(?:a520|a620|b450|b550|b650|b660|b760|x570|x670|z690|z790|h610|h770)\b', alvo_norm):
            return 'placa_mae'

    # SSD/armazenamento tem prioridade — 'PS5'/'PC' em 'SSD ... PS5 e PC'
    # é só compatibilidade, não console.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:ssd|nvme|m\.2|hard\s*disk|disco\s*rigido|armazenamento|sata)\b', alvo_norm):
            return 'ssd'

    # Cooler/air cooler/water cooler tem prioridade — 'torre' do cooler
    # (torre de dissipação) não deve virar gabinete.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:air\s*cooler|water\s*cooler|watercooler|dissipador|cooler\b.*torre|torre\b.*cooler|ventoinha|cooler\b.*ventilador|ventilador\b.*cooler|cooler\s*para\s*processador|processador\s*cooler)\b', alvo_norm):
            return 'cooler'

    # Microfone tem prioridade sobre 'headset'/'fone de ouvido' citados como
    # recurso ('Microfone FIFINE ... Fone de Ouvido, Microfone USB Condensador'
    # é um MICROFONE, não um headset). Mas 'Headset ... com Microfone' é um
    # headset com microfone embutido, não um microfone avulso.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        eh_headset = re.search(r'\b(?:headset|headphone|fone\s*de\s*ouvido|fone\b|fones\b|auricular|earbuds?)\b', alvo_norm)
        if eh_headset and not re.search(r'\bmicrofone\s*(?:de|dedicado|avulso|usb|condensador|gamer)\b', alvo_norm):
            continue  # é headset/fone com microfone embutido
        # 'Webcam ... Com Microfone' — o microfone é embutido na webcam, não
        # um microfone avulso. O produto é a WEBCAM.
        if re.search(r'\bwebcam\b', alvo_norm):
            continue
        if re.search(r'\bmicrofone\b', alvo_norm) and \
           re.search(r'\b(?:microfone|usb|condensador|gamer|streaming|gravac|fifine|modmic|de\s*lapela)\b', alvo_norm):
            return 'microfone'

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
        if re.search(r'\b(?:carregador|adaptador|usb\s*c|cable)\b', alvo_norm) or \
           re.search(r'\bcabo\b.*\b(?:usb|hdmi|energia|carregador|tipo)\b', alvo_norm):
            continue  # cabo/carregador; 'macbook/iphone' é só compatibilidade
        if re.search(r'\b(?:para|compat[ií]vel|com|pc\s*e|pc\b|no\s*pc)\s*(?:pc\s*e\s*)?(?:notebook|laptop)\b', alvo_norm):
            continue  # é compatibilidade, não anúncio de notebook
        if re.search(r'\b(?:notebook|laptop|macbook|ultrabook|chromebook|galaxy\s*book)\b', alvo_norm):
            return 'notebook'

    # TV tem prioridade sobre 'jogo'/'sports'/'controle'/'processador' citados:
    # 'Smart TV ... Modo Jogo Pro', 'TV ... Modo Esportes', 'Smart TV ...
    # Controle AI Magic', 'TV ... Processador a7' — tudo é atributo da TV.
    # Mas 'Monitor Odyssey OLED G5' é um MONITOR, não uma TV (OLED/QLED aqui é
    # do painel do monitor).
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        eh_monitor = re.search(r'\bmonitor\b', alvo_norm)
        if eh_monitor and re.search(r'\b(?:monitor|144hz|165hz|180hz|240hz|280hz|360hz|0\.[0-9]*ms|dp\b|displayport|freesync|gsync)\b', alvo_norm):
            continue  # é monitor; 'oled'/'qled' é o painel, não uma TV
        if re.search(r'\b(?:smart\s*tv|televis|tv\s*\d{2}|tv\b.{0,40}?\b\d{2}\s*(?:pol|polegadas|polegada)|tv\b(?!\s*box).{0,40}?\b\d{2}\b|qled|oled|miniled|neo\s*qled)\b', alvo_norm):
            return 'tv'

    # Monitor tem prioridade — 'Monitor Odyssey OLED G5' é um monitor mesmo
    # com 'oled'/'qled' no título (que viraria 'tv' no loop de categorias).
    # Acessórios de monitor ('Suporte Para Monitores Articulado', 'braço
    # para monitor', 'suporte tv monitor') também contam como monitor.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\bmonitor\b', alvo_norm):
            return 'monitor'
        if re.search(r'\bsuporte\b.*\b(?:monitor|monitores|tv)\b', alvo_norm) or \
           re.search(r'\b(?:monitor|monitores)\b.*\bsuporte\b', alvo_norm):
            return 'monitor'

    # Teclado tem prioridade sobre 'cabo' — 'Teclado ... com cabo USB Tipo-C'
    # é um TECLADO; o 'cabo' é só o modo de conexão, não um cabo avulso.
    for alvo in (titulo, texto,):
        if not alvo:
            continue
        alvo_norm = _norm(_limpar_compat(alvo))
        if not alvo_norm:
            continue
        if re.search(r'\b(?:teclado|keyboard)\b', alvo_norm):
            return 'teclado'

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
            # Anúncio de cupom que fala de resgate de cupons (sem % OFF no texto):
            # 'Teremos vários cupons no Mercado Livre hoje...', 'cupons sairão
            # nos horários', 'ative a notificação e resgate' → é um cupom.
            eh_anuncio_cupom_env = re.search(
                r'cupons?\b.{0,80}\b(?:mercado livre|hoje|sair[aá]o|horari|notifica|resgate|dispon[ií]vel|ativo)',
                texto_baixo,
            )
            if tem_off and (tem_limite or tem_cupom):
                return 'cupom'
            if tem_cupom and eh_anuncio_cupom_env:
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
