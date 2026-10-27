from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_requests, name='my_requests'),
    path('<int:pk>/cancel/', views.cancel_request, name='cancel_request'),
]