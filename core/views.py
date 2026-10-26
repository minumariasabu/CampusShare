from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from borrowing.models import Notification, Request as BorrowRequest
from resources.models import Category, Resource


def home(request):
    categories = Category.objects.all()
    return render(request, 'core/home.html', {'categories': categories})


@login_required
def dashboard(request):
    user = request.user
    today = timezone.localdate()

    active_listings = Resource.objects.filter(owner=user, is_hidden=False).count()
    pending_requests = BorrowRequest.objects.filter(
        resource__owner=user, status='pending'
    ).count()
    items_borrowed = BorrowRequest.objects.filter(
        borrower=user, status__in=['handed_over', 'return_initiated', 'overdue']
    ).count()
    due_soon = BorrowRequest.objects.filter(
        borrower=user, status='handed_over',
        return_by__isnull=False, return_by__lte=today + timedelta(days=3),
    ).count()
    notifications = Notification.objects.filter(user=user)[:5]

    context = {
        'active_listings': active_listings,
        'pending_requests': pending_requests,
        'items_borrowed': items_borrowed,
        'due_soon': due_soon,
        'notifications': notifications,
    }
    return render(request, 'core/dashboard.html', context)