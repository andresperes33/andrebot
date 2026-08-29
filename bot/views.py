from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db import models as _db_models
from datetime import timedelta
from .models import Promo, Artigo

# Lojas sempre exibidas no filtro, mesmo sem promoções no período atual.
_LOJAS_FIXAS = [
    'Shopee', 'Amazon', 'AliExpress', 'Mercado Livre', 'KaBuM',
    'Magazine Luíza', 'Pichau', 'Terabyte', 'Americanas', 'Casas Bahia',
]

# Descrições originais por categoria — conteúdo próprio que ajuda na
# indexação e na aprovação do AdSense (texto escrito, não réplica de oferta).
_CATEGORIA_DESCRICOES = {
    'ssd': 'SSDs e HDs com o melhor preço: NVMe, SATA e M.2 para dar mais velocidade ao seu PC. Encontramos ofertas de armazenamento para upgrade rápido e barato.',
    'placa_video': 'Placas de vídeo NVIDIA GeForce e AMD Radeon para jogar e renderizar. Acompanhamos RTX, GTX e RX com os menores preços do mercado brasileiro.',
    'placa_mae': 'Placas-mãe para todas as plataformas: Intel e AMD, sockets AM4, AM5, LGA. Modelos econômicos e gamer em oferta.',
    'processador': 'Processadores Intel Core e AMD Ryzen para montar ou turbinar seu PC. Do básico ao topo de linha, com os melhores valores encontrados.',
    'memoria_ram': 'Memória RAM DDR4 e DDR5 em promoção. Kits de memória para melhorar o desempenho do seu computador sem gastar muito.',
    'kit': 'Kits de montagem com placa-mãe, processador e memória juntos. A forma mais econômica de montar um PC do zero.',
    'notebook': 'Notebooks e laptops para estudo, trabalho e jogos. Ultrabooks, gamer e convencionais com as melhores ofertas.',
    'monitor': 'Monitores com taxas de atualização de 144Hz, 165Hz, 240Hz e mais. Full HD, QHD e ultrawide para melhorar sua experiência.',
    'celular': 'Celulares e smartphones Android com o menor preço: Xiaomi, Samsung, Motorola e mais. Confira antes de comprar.',
    'tv': 'Smart TVs e televisores 4K, QLED e OLED com preços imperdíveis para assistir seus conteúdos com a melhor imagem.',
    'caixa_som': 'Caixas de som e soundbars Bluetooth com potência para sua música, casa e festas. Encontramos os melhores preços em caixas de som.',
    'headset': 'Headsets e fones de ouvido para jogos e música, com ou sem fio, microfone e cancelamento de ruído.',
    'teclado': 'Teclados mecânicos e membranas para melhorar sua digitação e jogatina. Switches, RGB e designs gamer.',
    'mouse': 'Mouses gamer e de escritório com alta precisão, DPI ajustável e design ergonômico para todas as tarefas.',
    'mousepad': 'Mousepads grandes e de alta qualidade para precisão nos jogos e conforto no dia a dia.',
    'cadeira': 'Cadeiras gamers e ergonômicas para cuidar da sua postura nas longas horas de trabalho e gameplay.',
    'impressora': 'Impressoras e multifuncionais com toner e tinta em promoção para uso doméstico e de escritório.',
    'fonte': 'Fontes de alimentação com certificação e wattagem para PC. Eficiência e estabilidade para seu hardware.',
    'gabinete': 'Gabinetes e torres com boa ventilação, vidro temperado e espaços para o seu setup crescer.',
    'cooler': 'Coolers e water coolers para manter seu processador refrigerado com silêncio e eficiência.',
    'pasta_termica': 'Pastas térmicas de alta condutividade para processador e placa de vídeo. Comprando em promoção, você melhora a refrigeração do seu PC.',
    'controle': 'Controles e gamepads para PC e consoles de última geração, com fio ou bluetooth.',
    'webcam': 'Webcams de alta resolução para reuniões, lives e streaming com boa imagem.',
    'microfone': 'Microfones para streaming, podcast e gravação, dinâmicos e condensadores, com ótima captação de voz.',
    'roteador': 'Roteadores Wi-Fi 6 e mesh para internet rápida e estável em todos os cômodos da casa.',
    'console': 'Consoles de videogame e handhelds em oferta, com os melhores preços para os gamers.',
    'jogo': 'Jogos físicos e códigos digitais para PlayStation, Xbox, Nintendo Switch e PC. Encontramos as maiores promoções dos lançamentos.',
    'cupom': 'Cupons de desconto para usar nas maiores lojas do país. Garanta um desconto a mais nas suas compras.',
    'outros': 'Ofertas de tecnologia e periféricos variados que não se encaixam nas demais categorias.',
}


def promo_detail_view(request, pk):
    """
    Página individual de uma promoção.
    Mostra foto, preço, cupom, texto original com links e meta tags de compartilhamento.
    """
    import re
    from bot.services import _RODAPE_CANAIS_HTML
    promo = get_object_or_404(Promo, pk=pk)
    recentes = Promo.objects.exclude(pk=pk)[:3]

    # Histórico de preços: mesmas promoções do mesmo produto (mesmo link),
    # com preço preenchido. Deduplicado por preço — cada valor aparece UMA
    # vez com a data mais recente, para não virar lista infinita quando a
    # mesma oferta é repostada (dedup desligado).
    historico = []
    chart_data = []

    def _normalizar_preco(p):
        # 'R$ 335,00' -> 335.00 ; 'R$335' -> 335.0
        m = re.search(r'R\$\s*(\d[\d.,]*)', p or '')
        if not m:
            return None
        v = m.group(1).replace('.', '').replace(',', '.')
        try:
            return round(float(v), 2)
        except ValueError:
            return None

    if promo.produto_chave:
        linhas = list(
            Promo.objects
            .filter(produto_chave=promo.produto_chave)
            .exclude(preco='')
            .order_by('criado_em')
            .values('preco', 'criado_em', 'pk', 'loja', 'link_afiliado')
        )
        if promo.preco:
            linhas.append({
                'preco': promo.preco, 'criado_em': promo.criado_em,
                'pk': promo.pk, 'loja': promo.loja, 'link_afiliado': promo.link_afiliado,
            })

        # Agrupa por valor numérico; mantém a entrada mais recente.
        por_valor = {}
        for item in linhas:
            v = _normalizar_preco(item['preco'])
            if v is None:
                continue
            # Como linhas está ordenada asc por data, sobrescrever faz a
            # entrada mais recente de cada valor vencer.
            por_valor[v] = item

        # Ordena pela data da ocorrência mais recente de cada valor.
        for item in sorted(por_valor.values(), key=lambda it: it['criado_em']):
            historico.append(item)
            chart_data.append({
                'data': item['criado_em'].isoformat(),
                'valor': _normalizar_preco(item['preco']),
            })

    return render(request, 'bot/promo_detail.html', {
        'promo': promo,
        'recentes': recentes,
        'historico': historico,
        'chart_data': chart_data,
        'rodape_canais': _RODAPE_CANAIS_HTML,
    })


def promos_view(request):
    """
    Página pública de promoções.
    Filtra por: data (hoje/semana/mês), categoria e busca por texto.
    Suporta paginação por "Ver mais" (offset) e resposta AJAX parcial
    para carregar mais cards sem recarregar a página.
    """
    LIMITE = 12
    promos = Promo.objects.all()

    # Filtro de data — usa horário de Brasília (America/Sao_Paulo)
    periodo = request.GET.get('periodo', 'hoje')
    agora = timezone.localtime(timezone.now())   # converte UTC → Brasília
    if periodo == 'hoje':
        promos = promos.filter(criado_em__date=agora.date())
    elif periodo == 'semana':
        promos = promos.filter(criado_em__gte=agora - timedelta(days=7))
    elif periodo == 'mes':
        promos = promos.filter(criado_em__gte=agora - timedelta(days=30))

    # Filtro de categoria
    categoria = request.GET.get('cat', '')
    if categoria:
        promos = promos.filter(categoria=categoria)

    # Loja da semana/mês atual (para os filtros exibidos).
    # Calculado ANTES de aplicar o filtro de loja, para todas as lojas ficarem visíveis.
    lojas_bd = list(promos.exclude(loja='').order_by('loja').values_list('loja', flat=True).distinct())
    # As lojas fixas (KaBuM etc.) sempre aparecem, mesmo sem promoções no período.
    lojas = list(_LOJAS_FIXAS) + [l for l in lojas_bd if l not in _LOJAS_FIXAS]

    # Filtro por loja
    loja = request.GET.get('loja', '')
    if loja:
        promos = promos.filter(loja=loja)

    # Busca por texto
    q = request.GET.get('q', '')
    if q:
        promos = promos.filter(titulo__icontains=q) | Promo.objects.filter(texto_original__icontains=q)

    promos = promos.order_by('-criado_em')
    total = promos.count()

    # "Ver mais": carrega a partir de um offset
    try:
        offset = max(int(request.GET.get('offset', '0')), 0)
    except (TypeError, ValueError):
        offset = 0

    busca_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' and bool(request.GET.get('offset'))
    pagina = promos[offset:offset + LIMITE]
    tem_mais = total > (offset + len(pagina))

    if busca_ajax:
        return render(request, 'bot/_promo_grid_page.html', {
            'promos': pagina,
            'offset': offset,
            'tem_mais': tem_mais,
            'total': total,
        })

    categorias = Promo.CATEGORIA_CHOICES
    categorias_guia = [
        {'slug': slug, 'nome': nome, 'desc': _CATEGORIA_DESCRICOES.get(slug, '')}
        for slug, nome in categorias
        if _CATEGORIA_DESCRICOES.get(slug, '')
    ]

    # Artigos recentes do Blog (destaque na home, acima do guia de categorias)
    artigos_blog = list(Artigo.objects.filter(publicado=True)[:4])

    return render(request, 'bot/promos.html', {
        'promos': pagina,
        'periodo': periodo,
        'categoria_ativa': categoria,
        'categorias': categorias,
        'lojas': lojas,
        'loja_ativa': loja,
        'q': q,
        'total': total,
        'offset': offset,
        'tem_mais': tem_mais,
        'LIMITE': LIMITE,
        'categorias_guia': categorias_guia,
        'artigos_blog': artigos_blog,
    })


def privacy_view(request):
    """
    Página de Política de Privacidade (Obrigatória para AdSense).
    """
    return render(request, 'bot/privacy.html')


def sobre_view(request):
    """
    Página 'Sobre' — quem é a Nitro Tech e como as ofertas funcionam.
    """
    return render(request, 'bot/sobre.html')


def contato_view(request):
    """
    Página 'Contato' — contato com o responsável pelo site.
    """
    return render(request, 'bot/contato.html')


def termos_view(request):
    """
    Página 'Termos de Uso' do site Nitro Tech.
    """
    return render(request, 'bot/termos.html')


def guia_view(request):
    """
    Lista de artigos/guias originais (conteúdo exclusivo para SEO e AdSense).
    Suporta busca por texto e filtro por categoria (com resposta AJAX).
    """
    from .models import Artigo

    artigos = Artigo.objects.filter(publicado=True)

    # Busca por texto (título/conteúdo)
    q = request.GET.get('q', '').strip()
    if q:
        artigos = artigos.filter(
            _db_models.Q(titulo__icontains=q) | _db_models.Q(conteudo__icontains=q)
        )

    # Filtro por categoria
    categoria = request.GET.get('cat', '').strip()
    if categoria:
        artigos = artigos.filter(categoria=categoria)

    artigos = artigos.order_by('-criado_em')

    # Resposta AJAX (busca/filtro) — só o grid
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'bot/_blog_grid.html', {'artigos': artigos})

    categorias = list(
        Artigo.objects.filter(publicado=True)
        .exclude(categoria='')
        .order_by('categoria')
        .values_list('categoria', flat=True)
        .distinct()
    )

    return render(request, 'bot/guia.html', {
        'artigos': artigos,
        'categorias': categorias,
        'categoria_ativa': categoria,
        'q': q,
    })


def guia_artigo_view(request, slug):
    """
    Página individual de um artigo/guiu + artigos relacionados (mesma categoria).
    """
    from .models import Artigo
    artigo = get_object_or_404(Artigo, slug=slug, publicado=True)
    relacionados = Artigo.objects.filter(
        publicado=True, categoria=artigo.categoria
    ).exclude(pk=artigo.pk)[:4]
    return render(request, 'bot/guia_artigo.html', {
        'artigo': artigo,
        'relacionados': relacionados,
    })


from django.http import HttpResponse


def nitroalerta_view(request):
    """
    Página do NITRO ALERTA: cadastro de alerta de produto por WhatsApp.
    GET mostra o formulário + explicação; POST cadastra o alerta.
    """
    from .models import AlertaSite
    from .services import normalizar_whatsapp

    sucesso = None
    erro = None

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        numero = request.POST.get('whatsapp', '').strip()
        keyword = request.POST.get('keyword', '').strip()

        if not numero:
            erro = 'Digite seu número de WhatsApp (DDD + número).'
        elif not keyword:
            erro = 'Digite qual produto você quer acompanhar.'
        else:
            wa = normalizar_whatsapp(numero)
            if len(wa) < 13:
                erro = 'Número inválido. Digite no formato: 38 999821883 (DDD + número).'
            else:
                AlertaSite.objects.create(
                    nome=nome,
                    whatsapp=wa,
                    keyword=keyword,
                )
                sucesso = f'Pronto, {nome or "cara"}! Vamos te avisar quando aparecer oferta de "{keyword}".'

    return render(request, 'bot/nitroalerta.html', {'sucesso': sucesso, 'erro': erro})


def robots_txt_view(request):
    """
    Gera o robots.txt dinamicamente.
    """
    base_url = request.build_absolute_uri('/').rstrip('/')
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "",
        f"Sitemap: {base_url}/sitemap.xml"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def ads_txt_view(request):
    """
    Gera o ads.txt do Google AdSense (exigido para validar o site).
    """
    lines = [
        "google.com, pub-1945676049008537, DIRECT, f08c47fec0942fa0",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml_view(request):
    """
    Gera o sitemap.xml com as rotas principais e todas as páginas individuais de promo.
    """
    base_url = request.build_absolute_uri('/').rstrip('/')
    pages = [
        {"loc": f"{base_url}/promos/", "changefreq": "always", "priority": "1.0"},
        {"loc": f"{base_url}/blog/", "changefreq": "weekly", "priority": "0.7"},
        {"loc": f"{base_url}/nitro-alerta/", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/sobre/", "changefreq": "monthly", "priority": "0.3"},
        {"loc": f"{base_url}/contato/", "changefreq": "monthly", "priority": "0.3"},
        {"loc": f"{base_url}/termos-de-uso/", "changefreq": "monthly", "priority": "0.3"},
        {"loc": f"{base_url}/politica-de-privacidade/", "changefreq": "monthly", "priority": "0.3"},
    ]

    # Artigos/Guia do site (conteúdo original indexável)
    for artigo in Artigo.objects.filter(publicado=True):
        pages.append({
            "loc": f"{base_url}/blog/{artigo.slug}/",
            "changefreq": "monthly",
            "priority": "0.7",
        })

    # Cada promo vira uma página individual indexável
    for promo in Promo.objects.all()[:500]:
        pages.append({
            "loc": f"{base_url}/promos/{promo.pk}/",
            "changefreq": "weekly",
            "priority": "0.8",
        })

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for p in pages:
        xml.append('  <url>')
        xml.append(f'    <loc>{p["loc"]}</loc>')
        xml.append(f'    <changefreq>{p["changefreq"]}</changefreq>')
        xml.append(f'    <priority>{p["priority"]}</priority>')
        xml.append('  </url>')
    xml.append('</urlset>')
    
    return HttpResponse("\n".join(xml), content_type="application/xml")
