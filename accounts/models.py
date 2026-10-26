from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class Institution(models.Model):
    name = models.CharField(max_length=200)
    email_domain = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class User(AbstractUser):
    # Django already gives: password, is_active, is_staff (use as admin), date_joined
    email = models.EmailField(unique=True)
    institution = models.ForeignKey(Institution, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.CharField(max_length=100, blank=True)
    year = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to='profiles/', blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.email
