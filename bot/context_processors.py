from bot.services import site_base_url


def site_url(request):
    """
    Injeta o domínio da aplicação (detectado automaticamente da request)
    para uso nas meta tags (OG/Twitter) e links absolutos.
    Sempre em HTTPS.
    """
    return {'SITE_URL': site_base_url(request)}