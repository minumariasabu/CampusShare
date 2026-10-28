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
    path('<int:pk>/return/', views.return_item, name='return_item'),
    path('<int:pk>/confirm-return/', views.confirm_return, name='confirm_return'),
    path('<int:pk>/review/', views.review_request, name='review_request'),
]

