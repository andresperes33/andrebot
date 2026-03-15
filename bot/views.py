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

    import json
    for promo in promos:
        promo.cupons_lista = []
        if promo.cupom:
            try:
                cupons_parsed = json.loads(promo.cupom)
                if isinstance(cupons_parsed, list):
                    promo.cupons_lista = cupons_parsed
                else:
                    promo.cupons_lista.append({"regra": "Cupom de Desconto", "codigo": promo.cupom})
            except (json.JSONDecodeError, TypeError):
                # Compatibilidade com promoções antigas salvas como string simples
                promo.cupons_lista.append({"regra": "Cupom de Desconto", "codigo": promo.cupom})

    return render(request, 'bot/promos.html', {
        'promos': promos,
        'periodo': periodo,
        'categoria_ativa': categoria,
        'categorias': categorias,
        'q': q,
        'total': promos.count(),
    })
