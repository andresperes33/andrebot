from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from .models import Promo


def promos_view(request):
    """
    Página pública de promoções.
    Filtra por: data (hoje/semana/mês), categoria e busca por texto.
    """
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

    # Busca por texto
    q = request.GET.get('q', '')
    if q:
        promos = promos.filter(titulo__icontains=q) | Promo.objects.filter(texto_original__icontains=q)

    promos = promos.order_by('-criado_em')[:100]

    categorias = Promo.CATEGORIA_CHOICES

    # Não é mais necessário processar cupons ou links complexos
    pass

    return render(request, 'bot/promos.html', {
        'promos': promos,
        'periodo': periodo,
        'categoria_ativa': categoria,
        'categorias': categorias,
        'q': q,
        'total': promos.count(),
    })


def privacy_view(request):
    """
    Página de Política de Privacidade (Obrigatória para AdSense).
    """
    return render(request, 'bot/privacy.html')


from django.http import HttpResponse

def ads_txt_view(request):
    """
    Serve o arquivo ads.txt na raiz.
    ID de Editor do usuário: ca-pub-1945676049008537
    """
    content = "google.com, pub-1945676049008537, DIRECT, f08c47fec0942fa0"
    return HttpResponse(content, content_type="text/plain")


def robots_txt_view(request):
    """
    Gera o robots.txt dinamicamente.
    """
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "",
        "Sitemap: https://promos.andreindica.com.br/sitemap.xml"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml_view(request):
    """
    Gera o sitemap.xml com as rotas principais.
    """
    # Em um cenário real com páginas individuais para cada promo, 
    # listaríamos todas aqui. Como o site é uma single page de promos,
    # listaremos as rotas fixas.
    base_url = "https://promos.andreindica.com.br"
    pages = [
        {"loc": f"{base_url}/promos/", "changefreq": "always", "priority": "1.0"},
        {"loc": f"{base_url}/politica-de-privacidade/", "changefreq": "monthly", "priority": "0.3"},
    ]
    
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
