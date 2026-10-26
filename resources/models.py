from django.conf import settings
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Resource(models.Model):
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('worn', 'Worn'),
    ]
    LISTING_TYPE_CHOICES = [
        ('borrow', 'Borrow'),
        ('donate', 'Donate'),
        ('exchange', 'Exchange'),
    ]
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('lent_out', 'Lent out'),
        ('unavailable', 'Unavailable'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='resources'
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name='resources'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default='good')
    listing_type = models.CharField(max_length=10, choices=LISTING_TYPE_CHOICES, default='borrow')
    max_borrow_days = models.PositiveIntegerField(default=7)
    pickup_location = models.CharField(max_length=200)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='available')
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class ResourceImage(models.Model):
    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name='images'
    )
    image = models.ImageField(upload_to='resources/')

    def __str__(self):
        return f"Image for {self.resource.title}"