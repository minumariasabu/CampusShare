from django.urls import path
from . import views

urlpatterns = [
    path('', views.notifications, name='notifications'),
    path('read-all/', views.mark_all_read, name='mark_all_read'),
    path('<int:pk>/open/', views.open_notification, name='open_notification'),
]