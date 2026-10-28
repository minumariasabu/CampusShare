from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='admin_dashboard'),
    path('users/', views.manage_users, name='admin_users'),
    path('users/<int:pk>/', views.user_detail, name='admin_user_detail'),
    path('users/<int:pk>/toggle/', views.toggle_user, name='admin_user_toggle'),
    path('users/<int:pk>/delete/', views.delete_user, name='admin_user_delete'),
]