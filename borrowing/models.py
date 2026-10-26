from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from resources.models import Resource


class Request(models.Model):
    TYPE_CHOICES = [
        ('borrow', 'Borrow'),
        ('donate', 'Donate'),
        ('exchange', 'Exchange'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('handed_over', 'Handed over'),
        ('return_initiated', 'Return initiated'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('overdue', 'Overdue'),
    ]
    RETURN_CONDITION_CHOICES = [
        ('good', 'Good'),
        ('damaged', 'Damaged'),
        ('missing_parts', 'Missing parts'),
    ]

    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name='requests'
    )
    borrower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='requests_made'
    )
    request_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='borrow')
    needed_from = models.DateField()
    return_by = models.DateField(null=True, blank=True)
    message = models.TextField(blank=True)
    exchange_offer = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reject_reason = models.TextField(blank=True)
    return_condition = models.CharField(
        max_length=20, choices=RETURN_CONDITION_CHOICES, blank=True
    )
    return_notes = models.TextField(blank=True)
    handed_over_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.borrower} -> {self.resource.title} ({self.status})"


class Review(models.Model):
    request = models.ForeignKey(
        Request, on_delete=models.CASCADE, related_name='reviews'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_given'
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_received'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('request', 'reviewer')

    def __str__(self):
        return f"{self.reviewer} rated {self.reviewee}: {self.rating}/5"


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    request = models.ForeignKey(
        Request, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications'
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"To {self.user}: {self.message}"


class Complaint(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='complaints_filed'
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='complaints_against'
    )
    resource = models.ForeignKey(
        Resource, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaints'
    )
    reason = models.CharField(max_length=100)
    description = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Complaint by {self.reporter}: {self.reason}"