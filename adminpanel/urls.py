from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='admin_dashboard'),
    path('users/', views.manage_users, name='admin_users'),
    path('users/<int:pk>/', views.user_detail, name='admin_user_detail'),
    path('users/<int:pk>/toggle/', views.toggle_user, name='admin_user_toggle'),
    path('users/<int:pk>/delete/', views.delete_user, name='admin_user_delete'),
    path('listings/', views.manage_listings, name='admin_listings'),
    path('listings/<int:pk>/toggle/', views.toggle_listing, name='admin_listing_toggle'),
    path('listings/<int:pk>/delete/', views.delete_listing, name='admin_listing_delete'),
    path('categories/', views.manage_categories, name='admin_categories'),
    path('categories/<int:pk>/edit/', views.edit_category, name='admin_category_edit'),
    path('categories/<int:pk>/delete/', views.delete_category, name='admin_category_delete'),
    path('complaints/', views.manage_complaints, name='admin_complaints'),
    path('complaints/<int:pk>/', views.complaint_detail, name='admin_complaint_detail'),
    path('complaints/<int:pk>/action/', views.complaint_action, name='admin_complaint_action'),
    path('reports/', views.reports, name='admin_reports'),
]
