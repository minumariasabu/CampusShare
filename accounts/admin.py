from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Institution, User


@admin.register(User)
class CampusUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('CampusShare', {
            'fields': ('institution', 'department', 'year', 'phone', 'photo', 'is_verified'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('CampusShare', {'fields': ('email', 'is_verified')}),
    )
    list_display = ('username', 'email', 'first_name', 'is_verified', 'is_staff', 'is_active')
    list_filter = UserAdmin.list_filter + ('is_verified',)


admin.site.register(Institution)