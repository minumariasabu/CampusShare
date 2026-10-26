from django.contrib import admin
from .models import Request, Review, Notification, Complaint

admin.site.register(Request)
admin.site.register(Review)
admin.site.register(Notification)
admin.site.register(Complaint)