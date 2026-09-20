"""
Middleware de redirect 301 permanente.

Qualquer requisição que chegar pelo domínio antigo (nitrotech.store)
é redirecionada para o novo domínio (promos.andreindicatech.com.br),
preservando o path completo e a query string.

Exemplos:
  www.nitrotech.store/promos/              → promos.andreindicatech.com.br/promos/
  www.nitrotech.store/promos/9716/teclado → promos.andreindicatech.com.br/promos/9716/teclado
  nitrotech.store/sobre/                  → promos.andreindicatech.com.br/sobre/
"""

from django.http import HttpResponsePermanentRedirect

# Domínios antigos que devem ser redirecionados
OLD_DOMAINS = {
    'www.nitrotech.store',
    'nitrotech.store',
}

NEW_DOMAIN = 'https://promos.andreindicatech.com.br'


class DomainRedirectMiddleware:
    """Redireciona 301 do domínio antigo para o novo, preservando path e query string."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]  # Remove porta, se houver

        if host in OLD_DOMAINS:
            # Monta a URL de destino: novo domínio + path original + query string
            new_url = NEW_DOMAIN + request.get_full_path()
            return HttpResponsePermanentRedirect(new_url)

        return self.get_response(request)

