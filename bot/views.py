from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import Promo


def promo_detail_view(request, pk):
    """
    Página individual de uma promoção.
    Mostra foto, preço, cupom, texto original com links e meta tags de compartilhamento.
    """
    promo = get_object_or_404(Promo, pk=pk)
    recentes = Promo.objects.exclude(pk=pk)[:3]
    return render(request, 'bot/promo_detail.html', {
        'promo': promo,
        'recentes': recentes,
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
    lojas = list(promos.exclude(loja='').order_by('loja').values_list('loja', flat=True).distinct())

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
    })


def privacy_view(request):
    """
    Página de Política de Privacidade (Obrigatória para AdSense).
    """
    return render(request, 'bot/privacy.html')


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


def sitemap_xml_view(request):
    """
    Gera o sitemap.xml com as rotas principais e todas as páginas individuais de promo.
    """
    base_url = request.build_absolute_uri('/').rstrip('/')
    pages = [
        {"loc": f"{base_url}/promos/", "changefreq": "always", "priority": "1.0"},
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
