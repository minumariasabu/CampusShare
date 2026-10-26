from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Institution, User

admin.site.register(Institution)
admin.site.register(User, UserAdmin)