from django.contrib import messages
from django.contrib.auth.decorators import login_required
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