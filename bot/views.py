from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import Promo

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
    'controle': 'Controles e gamepads para PC e consoles de última geração, com fio ou bluetooth.',
    'webcam': 'Webcams de alta resolução para reuniões, lives e streaming com boa imagem.',
    'roteador': 'Roteadores Wi-Fi 6 e mesh para internet rápida e estável em todos os cômodos da casa.',
    'console': 'Consoles de videogame e handhelds em oferta, com os melhores preços para os gamers.',
    'cupom': 'Cupons de desconto para usar nas maiores lojas do país. Garanta um desconto a mais nas suas compras.',
    'outros': 'Ofertas de tecnologia e periféricos variados que não se encaixam nas demais categorias.',
}


def promo_detail_view(request, pk):
    """
    Página individual de uma promoção.
    Mostra foto, preço, cupom, texto original com links e meta tags de compartilhamento.
    """
    from bot.services import _RODAPE_CANAIS_HTML
    promo = get_object_or_404(Promo, pk=pk)
    recentes = Promo.objects.exclude(pk=pk)[:3]

    # Histórico de preços: mesmas promoções do mesmo produto (mesmo link),
    # com preço preenchido, da mais antiga para a mais recente.
    historico = []
    if produto_chave := promo.produto_chave:
        historico = list(
            Promo.objects
            .filter(produto_chave=promo.produto_chave)
            .exclude(pk=pk)
            .exclude(preco='')
            .order_by('criado_em')
            .values('preco', 'criado_em')
        )

    return render(request, 'bot/promo_detail.html', {
        'promo': promo,
        'recentes': recentes,
        'historico': historico,
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


from django.http import HttpResponse


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
        {"loc": f"{base_url}/sobre/", "changefreq": "monthly", "priority": "0.3"},
        {"loc": f"{base_url}/contato/", "changefreq": "monthly", "priority": "0.3"},
        {"loc": f"{base_url}/termos-de-uso/", "changefreq": "monthly", "priority": "0.3"},
        {"loc": f"{base_url}/politica-de-privacidade/", "changefreq": "monthly", "priority": "0.3"},
    ]

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
