from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', RedirectView.as_view(url='/promos/', permanent=False)),
    path('promos/', views.promos_view, name='promos'),
    path('politica-de-privacidade/', views.privacy_view, name='privacy'),
    path('ads.txt', views.ads_txt_view, name='ads_txt'),
]
