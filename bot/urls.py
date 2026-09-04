from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', RedirectView.as_view(url='/promos/', permanent=False)),
    path('promos/', views.promos_view, name='promos'),
    path('promos/<int:pk>/', views.promo_detail_view, name='promo_detail'),
    path('politica-de-privacidade/', views.privacy_view, name='privacy'),
    path('sobre/', views.sobre_view, name='sobre'),
    path('contato/', views.contato_view, name='contato'),
    path('termos-de-uso/', views.termos_view, name='termos'),
    path('nitro-alerta/', views.nitroalerta_view, name='nitroalerta'),
    path('nitro-alerta/cancelar/<str:token>/', views.nitroalerta_cancelar_view, name='nitroalerta_cancelar'),
    path('blog/', views.guia_view, name='blog'),
    path('blog/<slug:slug>/', views.guia_artigo_view, name='blog_artigo'),
    path('avisos/', views.avisos_view, name='avisos'),
    path('avisos/<slug:slug>/', views.aviso_detail_view, name='aviso_detail'),
    # Redireciona a antiga URL /guia/ para /blog/ (sem quebrar links antigos)
    path('guia/', RedirectView.as_view(pattern_name='blog', permanent=False)),
    path('guia/<slug:slug>/', RedirectView.as_view(pattern_name='blog_artigo', permanent=False)),
    path('robots.txt', views.robots_txt_view, name='robots_txt'),
    path('ads.txt', views.ads_txt_view, name='ads_txt'),
    path('sitemap.xml', views.sitemap_xml_view, name='sitemap_xml'),
]
