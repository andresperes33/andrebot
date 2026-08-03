def site_url(request):
    """
    Injeta o domínio da aplicação (detectado automaticamente da request)
    para uso nas meta tags (OG/Twitter) e links absolutos.
    """
    return {'SITE_URL': request.build_absolute_uri('/').rstrip('/')}
