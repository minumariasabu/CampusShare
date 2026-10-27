from django.urls import path
from . import views

urlpatterns = [
    path('', views.browse, name='browse'),
    path('add/', views.add_resource, name='add_resource'),
    path('mine/', views.my_listings, name='my_listings'),
    path('<int:pk>/edit/', views.edit_resource, name='edit_resource'),
    path('<int:pk>/delete/', views.delete_resource, name='delete_resource'),
]