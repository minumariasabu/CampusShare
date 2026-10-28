from django.urls import path
from . import views

urlpatterns = [
    path('listing/<int:pk>/', views.report_listing, name='report_listing'),
    path('user/<int:pk>/', views.report_user, name='report_user'),
]