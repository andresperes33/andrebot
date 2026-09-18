from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', RedirectView.as_view(url='/promos/', permanent=False)),
    path('promos/', views.promos_view, name='promos'),
    path('promos/<int:pk>/<slug:slug>/', views.promo_detail_view, name='promo_detail'),
    # Redireciona a URL antiga /promos/<pk>/ para a URL com slug (301)
    path('promos/<int:pk>/', views.promo_detail_redirect_view, name='promo_detail_legacy'),
    path('politica-de-privacidade/', views.privacy_view, name='privacy'),
    path('sobre/', views.sobre_view, name='sobre'),
    path('contato/', views.contato_view, name='contato'),
    path('termos-de-uso/', views.termos_view, name='termos'),
    path('nitro-alerta/', views.nitroalerta_view, name='nitroalerta'),
    path('nitro-alerta/cancelar/<str:token>/', views.nitroalerta_cancelar_view, name='nitroalerta_cancelar'),
    path('robots.txt', views.robots_txt_view, name='robots_txt'),
    path('ads.txt', views.ads_txt_view, name='ads_txt'),
    path('sitemap.xml', views.sitemap_xml_view, name='sitemap_xml'),
    path('instagram/webhook/', views.instagram_webhook_view, name='instagram_webhook'),
]
