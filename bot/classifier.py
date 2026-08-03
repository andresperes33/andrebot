import re
import unicodedata


def sem_acento(texto):
    return unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode('ascii')


def _norm(texto):
    return re.sub(r'\s+', ' ', sem_acento(texto or '')).lower()


# Padrões por categoria, em ordem de prioridade (mais específica primeiro).
# Todos os padrões são aplicados sobre texto normalizado (sem acento, minúsculo).
_REGEX_CATEGORIA = [
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
    ('mouse', [
        r'\bmouse\b', r'\bmousepad\b',
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


def detectar_categoria(texto):
    """Classifica um texto de promoção em uma das categorias do site."""
    haystack = _norm(texto)
    if not haystack:
        return 'outros'
    for categoria, padroes in _REGEX_CATEGORIA:
        for p in padroes:
            if re.search(p, haystack):
                return categoria
    return 'outros'
