from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_requests, name='my_requests'),
    path('incoming/', views.incoming_requests, name='incoming_requests'),
    path('<int:pk>/', views.request_detail, name='request_detail'),
    path('<int:pk>/cancel/', views.cancel_request, name='cancel_request'),
    path('<int:pk>/accept/', views.accept_request, name='accept_request'),
    path('<int:pk>/reject/', views.reject_request, name='reject_request'),
    path('<int:pk>/received/', views.mark_received, name='mark_received'),
]