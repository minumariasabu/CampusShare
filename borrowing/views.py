from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.http import Http404
from django.utils import timezone

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

def build_timeline(req):
    """Turn a request's status into a list of steps: done, current or todo."""
    if req.status in ('rejected', 'cancelled'):
        return [
            {'label': 'Requested', 'state': 'done', 'when': req.created_at},
            {'label': req.get_status_display(), 'state': 'failed', 'when': None},
        ]

    if req.request_type == 'donate':
        steps = [
            ('Requested', req.created_at),
            ('Approved', None),
            ('Received', req.completed_at),
        ]
        position = {'pending': 0, 'approved': 1, 'completed': 2}
    else:
        steps = [
            ('Requested', req.created_at),
            ('Approved', None),
            ('Handed over', req.handed_over_at),
            ('Return initiated', None),
            ('Completed', req.completed_at),
        ]
        position = {
            'pending': 0, 'approved': 1, 'handed_over': 2, 'overdue': 2,
            'return_initiated': 3, 'completed': 4,
        }

    pos = position.get(req.status, 0)
    timeline = []
    for i, (label, when) in enumerate(steps):
        if req.status == 'completed' or i < pos:
            state = 'done'
        elif i == pos:
            state = 'current'
        else:
            state = 'todo'
        timeline.append({'label': label, 'state': state, 'when': when})
    return timeline


@login_required
def request_detail(request, pk):
    req = get_object_or_404(
        Request.objects.select_related('resource', 'resource__owner', 'borrower')
        .prefetch_related('resource__images'),
        pk=pk,
    )
    is_borrower = req.borrower_id == request.user.id
    is_owner = req.resource.owner_id == request.user.id

    # Only the two people involved may open this page
    if not (is_borrower or is_owner):
        raise Http404

    other = req.resource.owner if is_borrower else req.borrower
    show_contact = req.status in ('approved', 'handed_over', 'return_initiated', 'overdue')

    return render(request, 'borrowing/request_detail.html', {
        'req': req,
        'is_borrower': is_borrower,
        'is_owner': is_owner,
        'other': other,
        'show_contact': show_contact,
        'timeline': build_timeline(req),
    })


@login_required
@require_POST
def mark_received(request, pk):
    with transaction.atomic():
        req = get_object_or_404(
            Request.objects.select_for_update().select_related('resource'),
            pk=pk, borrower=request.user,
        )
        resource = req.resource

        if req.status != 'approved':
            messages.error(request, "This request isn't waiting for pickup.")
        elif resource.status != 'available':
            messages.error(
                request,
                "The owner has marked this item unavailable. Please contact the owner.",
            )
        else:
            now = timezone.now()
            req.handed_over_at = now
            who = request.user.first_name or "The borrower"

            if req.request_type == 'donate':
                # Nothing comes back, so the request is finished at handover
                req.status = 'completed'
                req.completed_at = now
                resource.status = 'unavailable'
                text = f'{who} received "{resource.title}". The donation is complete.'
            else:
                req.status = 'handed_over'
                resource.status = 'lent_out'
                text = f'{who} marked "{resource.title}" as received.'

            req.save(update_fields=['status', 'handed_over_at', 'completed_at'])
            resource.save(update_fields=['status'])
            notify(resource.owner, req, text)
            messages.success(request, "Marked as received. Enjoy the item!")

    return redirect('request_detail', pk=req.pk)

RETURNABLE_STATUSES = ('handed_over', 'overdue')


@login_required
def return_item(request, pk):
    req = get_object_or_404(
        Request.objects.select_related('resource', 'resource__owner')
        .prefetch_related('resource__images'),
        pk=pk, borrower=request.user,
    )

    # Donations are finished at handover, so there is nothing to return
    if req.request_type == 'donate' or req.status not in RETURNABLE_STATUSES:
        messages.error(request, "This item can't be returned right now.")
        return redirect('request_detail', pk=req.pk)

    if request.method == 'POST':
        with transaction.atomic():
            req = get_object_or_404(
                Request.objects.select_for_update().select_related('resource'),
                pk=pk, borrower=request.user,
            )
            if req.status not in RETURNABLE_STATUSES:
                messages.error(request, "This item can't be returned right now.")
                return redirect('request_detail', pk=req.pk)

            note = request.POST.get('note', '').strip()[:500]
            req.status = 'return_initiated'
            req.return_notes = note
            req.save(update_fields=['status', 'return_notes'])

            who = request.user.first_name or "The borrower"
            notify(
                req.resource.owner, req,
                f'{who} says "{req.resource.title}" has been returned. Please confirm.',
            )
        messages.success(request, "Return started. The owner has been asked to confirm.")
        return redirect('request_detail', pk=req.pk)

    return render(request, 'borrowing/return_item.html', {'req': req})

@login_required
def confirm_return(request, pk):
    req = get_object_or_404(
        Request.objects.select_related('resource', 'borrower')
        .prefetch_related('resource__images'),
        pk=pk, resource__owner=request.user,
    )

    if req.status != 'return_initiated':
        messages.error(request, "There is no return waiting for your confirmation.")
        return redirect('request_detail', pk=req.pk)

    error = None
    selected = ''

    if request.method == 'POST':
        selected = request.POST.get('condition', '')
        notes = request.POST.get('notes', '').strip()[:500]

        if selected not in dict(Request.RETURN_CONDITION_CHOICES):
            error = "Please choose the condition of the item."
        else:
            with transaction.atomic():
                req = get_object_or_404(
                    Request.objects.select_for_update().select_related('resource'),
                    pk=pk, resource__owner=request.user,
                )
                if req.status != 'return_initiated':
                    messages.error(request, "This return was already handled.")
                    return redirect('request_detail', pk=req.pk)

                resource = req.resource
                req.status = 'completed'
                req.completed_at = timezone.now()
                req.return_condition = selected
                req.owner_return_notes = notes
                req.save(update_fields=[
                    'status', 'completed_at', 'return_condition', 'owner_return_notes',
                ])

                # The item is back, so it can be requested again
                if resource.status == 'lent_out':
                    resource.status = 'available'
                    resource.save(update_fields=['status'])

                condition_text = req.get_return_condition_display().lower()
                notify(
                    req.borrower, req,
                    f'Your return of "{resource.title}" was confirmed. '
                    f'The owner marked it as: {condition_text}.',
                )

            if selected == 'good':
                messages.success(request, "Return confirmed. The item is available again.")
            else:
                messages.warning(
                    request,
                    "Return confirmed, and the item is available again. "
                    "If it needs repair, edit the listing and turn availability off.",
                )
            return redirect('request_detail', pk=req.pk)

    return render(request, 'borrowing/confirm_return.html', {
        'req': req,
        'condition_choices': Request.RETURN_CONDITION_CHOICES,
        'selected': selected,
        'error': error,
    })