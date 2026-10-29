from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import transaction
from datetime import date

from django.db.models.functions import TruncMonth
from django.utils import timezone
from borrowing.models import Complaint, Notification, Request as BorrowRequest, Review
from resources.models import Category, Resource

from .decorators import staff_required
from .forms import CategoryForm

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
        nxt = request.POST.get('next', '')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect('admin_users')


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

@staff_required
def manage_listings(request):
    qs = (
        Resource.objects.select_related('owner', 'category')
        .prefetch_related('images')
        .annotate(
            open_complaints=Count('complaints', filter=Q(complaints__status='open'), distinct=True),
            request_count=Count('requests', distinct=True),
        )
        .order_by('-open_complaints', '-created_at')      # flagged listings first
    )

    q = request.GET.get('q', '').strip()
    flt = request.GET.get('filter', '')

    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(owner__first_name__icontains=q)
            | Q(owner__email__icontains=q) | Q(category__name__icontains=q)
        )
    if flt == 'flagged':
        qs = qs.filter(open_complaints__gt=0)
    elif flt == 'hidden':
        qs = qs.filter(is_hidden=True)
    else:
        flt = ''

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)

    return render(request, 'adminpanel/listings.html', {
        'page_obj': page_obj,
        'total': paginator.count,
        'q': q,
        'filter': flt,
        'querystring': params.urlencode(),
    })


@staff_required
@require_POST
def toggle_listing(request, pk):
    resource = get_object_or_404(Resource.objects.select_related('owner'), pk=pk)
    resource.is_hidden = not resource.is_hidden
    resource.save(update_fields=['is_hidden'])

    if resource.is_hidden:
        text = f'Your listing "{resource.title}" was hidden by an admin. It is not visible to other students.'
        messages.success(request, "Listing hidden. The owner has been notified.")
    else:
        text = f'Your listing "{resource.title}" is visible to other students again.'
        messages.success(request, "Listing is visible again. The owner has been notified.")
    Notification.objects.create(user=resource.owner, message=text[:255])
    return redirect('admin_listings')


@staff_required
@require_POST
def delete_listing(request, pk):
    resource = get_object_or_404(Resource.objects.select_related('owner'), pk=pk)

    if resource.requests.exists():
        messages.error(
            request,
            "This listing has requests, so it can't be removed without erasing "
            "other students' history. Hide it instead.",
        )
    else:
        Notification.objects.create(
            user=resource.owner,
            message=f'Your listing "{resource.title}" was removed by an admin.'[:255],
        )
        resource.delete()
        messages.success(request, "Listing removed. The owner has been notified.")
    return redirect('admin_listings')


@staff_required
def manage_categories(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category added.")
            return redirect('admin_categories')
    else:
        form = CategoryForm()

    categories = Category.objects.annotate(item_count=Count('resources')).order_by('name')
    return render(request, 'adminpanel/categories.html', {
        'form': form,
        'categories': categories,
    })


@staff_required
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated.")
            return redirect('admin_categories')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'adminpanel/category_edit.html', {
        'form': form,
        'category': category,
    })


@staff_required
@require_POST
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.resources.exists():
        messages.error(
            request,
            "This category still has listings, so it can't be deleted. "
            "Rename it instead, or wait until its listings are gone.",
        )
    else:
        category.delete()
        messages.success(request, "Category deleted.")
    return redirect('admin_categories')

COMPLAINT_ACTIONS = {
    'resolve': 'Resolved',
    'warn': 'User warned',
    'deactivate': 'User deactivated',
}


@staff_required
def manage_complaints(request):
    base = Complaint.objects.select_related('reporter', 'reported_user', 'resource')

    tab = request.GET.get('status', 'open')
    if tab not in ('open', 'resolved', 'all'):
        tab = 'open'

    qs = base if tab == 'all' else base.filter(status=tab)
    qs = qs.order_by('-created_at')

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'adminpanel/complaints.html', {
        'page_obj': page_obj,
        'tab': tab,
        'open_count': base.filter(status='open').count(),
        'resolved_count': base.filter(status='resolved').count(),
        'all_count': base.count(),
    })


@staff_required
def complaint_detail(request, pk):
    complaint = get_object_or_404(
        Complaint.objects.select_related(
            'reporter', 'reported_user', 'resource', 'resource__owner'
        ),
        pk=pk,
    )
    target = complaint.reported_user

    other_reports = 0
    if target:
        other_reports = (
            Complaint.objects.filter(reported_user=target).exclude(pk=complaint.pk).count()
        )

    is_open = complaint.status == 'open'
    can_act_on_user = (
        is_open and target is not None
        and target.pk != request.user.pk and not target.is_staff
    )

    return render(request, 'adminpanel/complaint_detail.html', {
        'complaint': complaint,
        'target': target,
        'other_reports': other_reports,
        'is_open': is_open,
        'can_warn': can_act_on_user,
        'can_deactivate': can_act_on_user and target.is_active,
    })


@staff_required
@require_POST
def complaint_action(request, pk):
    action = request.POST.get('action', '')
    note = request.POST.get('note', '').strip()[:500]

    if action not in COMPLAINT_ACTIONS:
        messages.error(request, "Unknown action.")
        return redirect('admin_complaint_detail', pk=pk)

    with transaction.atomic():
        complaint = get_object_or_404(Complaint.objects.select_for_update(), pk=pk)

        if complaint.status != 'open':
            messages.error(request, "This complaint was already handled.")
            return redirect('admin_complaint_detail', pk=complaint.pk)

        target = complaint.reported_user

        if action in ('warn', 'deactivate'):
            if target is None:
                messages.error(request, "The reported user no longer exists.")
                return redirect('admin_complaint_detail', pk=complaint.pk)
            blocked = _protected(request, target)
            if blocked:
                messages.error(request, blocked)
                return redirect('admin_complaint_detail', pk=complaint.pk)
            if action == 'deactivate' and not target.is_active:
                messages.error(request, "This user is already deactivated.")
                return redirect('admin_complaint_detail', pk=complaint.pk)

        if action == 'warn':
            Notification.objects.create(
                user=target,
                message=(
                    f'An admin has issued you a warning after a report: "{complaint.reason}". '
                    'Please follow the sharing rules. Repeated reports may lead to '
                    'your account being deactivated.'
                )[:255],
            )
        elif action == 'deactivate':
            target.is_active = False
            target.save(update_fields=['is_active'])

        label = COMPLAINT_ACTIONS[action]
        complaint.status = 'resolved'
        complaint.admin_note = f'{label}. {note}' if note else label
        complaint.save(update_fields=['status', 'admin_note'])

        Notification.objects.create(
            user=complaint.reporter,
            message=f'Your report ("{complaint.reason}") was reviewed by an admin and closed.'[:255],
        )

    messages.success(request, f"Complaint closed: {label.lower()}.")
    return redirect('admin_complaint_detail', pk=complaint.pk)

# A request counts as "borrowed" once the item has actually changed hands
LENT_STATUSES = ['handed_over', 'return_initiated', 'overdue', 'completed']


def _percent(value, top):
    return round(value * 100 / top) if top else 0


@staff_required
def reports(request):
    # 1. Most borrowed items
    top_items = list(
        Resource.objects.select_related('owner')
        .annotate(times=Count('requests', filter=Q(requests__status__in=LENT_STATUSES), distinct=True))
        .filter(times__gt=0)
        .order_by('-times', 'title')[:5]
    )
    item_top = top_items[0].times if top_items else 0
    items = [
        {'obj': r, 'value': r.times, 'pct': _percent(r.times, item_top)}
        for r in top_items
    ]

    # 2. Most active users (listings + requests made + requests received)
    people = (
        User.objects.filter(is_staff=False, is_active=True)
        .annotate(
            listed=Count('resources', distinct=True),
            made=Count('requests_made', distinct=True),
            received=Count('resources__requests', distinct=True),
        )
    )
    ranked = sorted(
        ((u, u.listed + u.made + u.received) for u in people),
        key=lambda pair: -pair[1],
    )
    ranked = [pair for pair in ranked if pair[1] > 0][:5]
    user_top = ranked[0][1] if ranked else 0
    users = [
        {'obj': u, 'value': total, 'pct': _percent(total, user_top)}
        for u, total in ranked
    ]

    # 3. Requests per month (last 6 months, including months with zero)
    today = timezone.localdate()
    months = []
    year, month = today.year, today.month
    for _ in range(6):
        months.append((year, month))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    months.reverse()

    start = date(months[0][0], months[0][1], 1)
    counts = {}
    monthly_rows = (
        BorrowRequest.objects.filter(created_at__date__gte=start)
        .annotate(m=TruncMonth('created_at'))
        .values('m')
        .annotate(n=Count('id'))
    )
    for row in monthly_rows:
        counts[(row['m'].year, row['m'].month)] = row['n']

    month_top = max((counts.get(key, 0) for key in months), default=0)
    monthly = [
        {
            'label': date(y, m, 1).strftime('%b %Y'),
            'value': counts.get((y, m), 0),
            'pct': _percent(counts.get((y, m), 0), month_top),
        }
        for y, m in months
    ]

    # 4. Category-wise usage (requests made on items in each category)
    cats = list(
        Category.objects.annotate(
            listings=Count('resources', distinct=True),
            reqs=Count('resources__requests', distinct=True),
        ).order_by('-reqs', 'name')
    )
    cat_top = cats[0].reqs if cats else 0
    categories = [
        {'obj': c, 'value': c.reqs, 'pct': _percent(c.reqs, cat_top)}
        for c in cats
    ]

    totals = {
        'requests': BorrowRequest.objects.count(),
        'completed': BorrowRequest.objects.filter(status='completed').count(),
        'reviews': Review.objects.count(),
        'avg_rating': Review.objects.aggregate(a=Avg('rating'))['a'],
    }

    return render(request, 'adminpanel/reports.html', {
        'items': items,
        'users': users,
        'monthly': monthly,
        'categories': categories,
        'totals': totals,
    })