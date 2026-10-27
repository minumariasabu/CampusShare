from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification, Request

# (tab key, label, statuses shown in that tab; None means "all")
TABS = [
    ('all', 'All', None),
    ('pending', 'Pending', ['pending']),
    ('approved', 'Approved', ['approved']),
    ('active', 'Active', ['handed_over', 'return_initiated', 'overdue']),
    ('completed', 'Completed', ['completed']),
    ('rejected', 'Rejected / Cancelled', ['rejected', 'cancelled']),
]


@login_required
def my_requests(request):
    base = (
        Request.objects.filter(borrower=request.user)
        .select_related('resource', 'resource__owner')
        .prefetch_related('resource__images')
        .order_by('-created_at')
    )

    statuses_by_tab = {key: statuses for key, _, statuses in TABS}
    tab = request.GET.get('tab', 'all')
    if tab not in statuses_by_tab:
        tab = 'all'

    tabs = []
    for key, label, statuses in TABS:
        count = base.count() if statuses is None else base.filter(status__in=statuses).count()
        tabs.append({'key': key, 'label': label, 'count': count})

    selected = statuses_by_tab[tab]
    my_reqs = base if selected is None else base.filter(status__in=selected)

    return render(request, 'borrowing/my_requests.html', {
        'my_reqs': my_reqs,
        'tabs': tabs,
        'current_tab': tab,
    })


@login_required
@require_POST
def cancel_request(request, pk):
    req = get_object_or_404(Request, pk=pk, borrower=request.user)

    if req.status != 'pending':
        messages.error(request, "Only pending requests can be cancelled.")
    else:
        req.status = 'cancelled'
        req.save(update_fields=['status'])
        who = request.user.first_name or "A student"
        Notification.objects.create(
            user=req.resource.owner,
            request=req,
            message=f'{who} cancelled the request for "{req.resource.title}".',
        )
        messages.success(request, "Your request has been cancelled.")
    return redirect('my_requests')

# Statuses that mean "this item is already promised to someone"
BLOCKING_STATUSES = ['approved', 'handed_over', 'return_initiated', 'overdue']


def notify(user, req, text):
    """Create a notification (the message column holds at most 255 characters)."""
    Notification.objects.create(user=user, request=req, message=text[:255])


@login_required
def incoming_requests(request):
    base = (
        Request.objects.filter(resource__owner=request.user)
        .select_related('resource', 'borrower')
        .prefetch_related('resource__images')
        .annotate(
            borrower_rating=Avg('borrower__reviews_received__rating'),
            borrower_review_count=Count('borrower__reviews_received', distinct=True),
        )
        .order_by('-created_at')
    )

    tab = request.GET.get('tab', 'pending')
    if tab not in ('pending', 'all'):
        tab = 'pending'

    pending_count = base.filter(status='pending').count()
    incoming = base.filter(status='pending') if tab == 'pending' else base

    return render(request, 'borrowing/incoming_requests.html', {
        'incoming': incoming,
        'current_tab': tab,
        'pending_count': pending_count,
        'all_count': base.count(),
    })


@login_required
@require_POST
def accept_request(request, pk):
    with transaction.atomic():
        req = get_object_or_404(
            Request.objects.select_for_update().select_related('resource'),
            pk=pk, resource__owner=request.user,
        )
        resource = req.resource

        if req.status != 'pending':
            messages.error(request, "This request is no longer pending.")
        elif resource.status != 'available':
            messages.error(
                request,
                "This item isn't marked available. Edit the listing and turn availability on first.",
            )
        elif Request.objects.filter(
            resource=resource, status__in=BLOCKING_STATUSES
        ).exclude(pk=req.pk).exists():
            messages.error(
                request,
                "You already approved another request for this item. "
                "Finish that one first, or reject this request.",
            )
        else:
            req.status = 'approved'
            req.save(update_fields=['status'])
            notify(
                req.borrower, req,
                f'Your request for "{resource.title}" was approved. '
                f'Pickup: {resource.pickup_location}.',
            )
            messages.success(request, "Request approved. The borrower has been notified.")
    return redirect('incoming_requests')


@login_required
@require_POST
def reject_request(request, pk):
    with transaction.atomic():
        req = get_object_or_404(
            Request.objects.select_for_update().select_related('resource'),
            pk=pk, resource__owner=request.user,
        )
        if req.status != 'pending':
            messages.error(request, "This request is no longer pending.")
        else:
            reason = request.POST.get('reason', '').strip()[:300]
            req.status = 'rejected'
            req.reject_reason = reason
            req.save(update_fields=['status', 'reject_reason'])
            text = f'Your request for "{req.resource.title}" was rejected.'
            if reason:
                text += f' Reason: {reason}'
            notify(req.borrower, req, text)
            messages.success(request, "Request rejected. The borrower has been notified.")
    return redirect('incoming_requests')