from django.urls import path
from . import views

urlpatterns = [
    path('promos/', views.promos_view, name='promos'),
]
