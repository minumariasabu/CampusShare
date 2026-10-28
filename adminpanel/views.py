from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from borrowing.models import Complaint, Request as BorrowRequest, Review
from resources.models import Resource

from .decorators import staff_required

User = get_user_model()

ACTIVE_STATUSES = ['approved', 'handed_over', 'return_initiated', 'overdue']


@staff_required
def dashboard(request):
    students = User.objects.filter(is_staff=False)

    stats = {
        'total_users': students.count(),
        'inactive_users': students.filter(is_active=False).count(),
        'total_listings': Resource.objects.count(),
        'hidden_listings': Resource.objects.filter(is_hidden=True).count(),
        'active_transactions': BorrowRequest.objects.filter(status__in=ACTIVE_STATUSES).count(),
        'pending_requests': BorrowRequest.objects.filter(status='pending').count(),
        'open_complaints': Complaint.objects.filter(status='open').count(),
    }

    return render(request, 'adminpanel/dashboard.html', {
        'stats': stats,
        'recent_requests': BorrowRequest.objects.select_related('resource', 'borrower')
                           .order_by('-created_at')[:5],
        'recent_complaints': Complaint.objects.select_related('reporter', 'reported_user', 'resource')
                             .order_by('-created_at')[:5],
        'new_users': students.order_by('-date_joined')[:5],
    })


@staff_required
def manage_users(request):
    qs = (
        User.objects.annotate(
            listing_count=Count('resources', distinct=True),
            request_count=Count('requests_made', distinct=True),
        )
        .order_by('-date_joined')
    )

    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')

    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) | Q(email__icontains=q)
            | Q(username__icontains=q) | Q(department__icontains=q)
        )
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)
    else:
        status = ''

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)

    return render(request, 'adminpanel/users.html', {
        'page_obj': page_obj,
        'total': paginator.count,
        'q': q,
        'status': status,
        'querystring': params.urlencode(),
    })


@staff_required
def user_detail(request, pk):
    target = get_object_or_404(User.objects.select_related('institution'), pk=pk)

    review_stats = Review.objects.filter(reviewee=target).aggregate(
        avg=Avg('rating'), count=Count('id')
    )

    return render(request, 'adminpanel/user_detail.html', {
        'target': target,
        'rating': review_stats['avg'],
        'review_count': review_stats['count'],
        'listing_count': target.resources.count(),
        'borrowed_count': target.requests_made.count(),
        'lent_count': BorrowRequest.objects.filter(resource__owner=target).count(),
        'complaints_filed': target.complaints_filed.count(),
        'complaints_against': target.complaints_against.count(),
        'listings': target.resources.order_by('-created_at')[:5],
        'requests_made': target.requests_made.select_related('resource').order_by('-created_at')[:5],
        'requests_received': BorrowRequest.objects.filter(resource__owner=target)
                             .select_related('resource', 'borrower').order_by('-created_at')[:5],
    })


def _protected(request, target):
    """Return a reason why this account can't be changed, or None if it can."""
    if target.pk == request.user.pk:
        return "You can't change your own account here."
    if target.is_staff:
        return "Admin accounts can't be changed from this page."
    return None


@staff_required
@require_POST
def toggle_user(request, pk):
    target = get_object_or_404(User, pk=pk)
    reason = _protected(request, target)
    if reason:
        messages.error(request, reason)
    else:
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        name = target.first_name or target.username
        if target.is_active:
            messages.success(request, f"{name} has been activated.")
        else:
            messages.success(request, f"{name} has been deactivated and can no longer log in.")
    return redirect(request.POST.get('next') or 'admin_users')


@staff_required
@require_POST
def delete_user(request, pk):
    target = get_object_or_404(User, pk=pk)
    reason = _protected(request, target)
    if reason:
        messages.error(request, reason)
        return redirect('admin_users')

    has_activity = (
        target.resources.exists()
        or target.requests_made.exists()
        or target.reviews_given.exists()
        or target.reviews_received.exists()
        or target.complaints_filed.exists()
        or target.complaints_against.exists()
    )
    if has_activity:
        messages.error(
            request,
            "This user has listings, requests, reviews or complaints, so they can't be deleted. "
            "Deactivate them instead.",
        )
        return redirect('admin_user_detail', pk=target.pk)

    name = target.first_name or target.username
    target.delete()
    messages.success(request, f"{name} has been deleted.")
    return redirect('admin_users')
