from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, render, redirect
from .forms import ResourceForm, ResourceEditForm
from .models import Category, Resource, ResourceImage
from django.http import Http404
from borrowing.forms import RequestForm, ACTIVE_STATUSES
from borrowing.models import Notification, Request as BorrowRequest, Review

MAX_IMAGES = 5


def check_images(images, already=0):
    """Return an error message if the photos are not acceptable, else None."""
    if already + len(images) > MAX_IMAGES:
        return f"A listing can have at most {MAX_IMAGES} photos."
    if any(not img.content_type.startswith('image/') for img in images):
        return "Only image files are allowed."
    return None


@login_required
def add_resource(request):
    image_error = None
    if request.method == 'POST':
        form = ResourceForm(request.POST)
        images = request.FILES.getlist('images')
        image_error = check_images(images)

        if form.is_valid() and not image_error:
            resource = form.save(commit=False)
            resource.owner = request.user
            resource.save()
            for img in images:
                ResourceImage.objects.create(resource=resource, image=img)
            messages.success(request, "Your item has been listed!")
            return redirect('my_listings')
    else:
        form = ResourceForm()
    return render(request, 'resources/add_resource.html', {
        'form': form,
        'image_error': image_error,
        'max_images': MAX_IMAGES,
    })


@login_required
def my_listings(request):
    resources = (
        Resource.objects.filter(owner=request.user)
        .annotate(request_count=Count('requests'))
        .prefetch_related('images')
        .order_by('-created_at')
    )
    return render(request, 'resources/my_listings.html', {'resources': resources})


@login_required
def edit_resource(request, pk):
    resource = get_object_or_404(Resource, pk=pk, owner=request.user)
    image_error = None

    if request.method == 'POST':
        form = ResourceEditForm(request.POST, instance=resource)
        new_images = request.FILES.getlist('images')
        remove_ids = [i for i in request.POST.getlist('remove_images') if i.isdigit()]
        remaining = resource.images.exclude(pk__in=remove_ids).count()
        image_error = check_images(new_images, already=remaining)

        if form.is_valid() and not image_error:
            form.save()
            resource.images.filter(pk__in=remove_ids).delete()
            for img in new_images:
                ResourceImage.objects.create(resource=resource, image=img)
            messages.success(request, "Your listing has been updated.")
            return redirect('my_listings')
    else:
        form = ResourceEditForm(instance=resource)

    return render(request, 'resources/edit_resource.html', {
        'form': form,
        'resource': resource,
        'images': resource.images.all(),
        'image_error': image_error,
        'max_images': MAX_IMAGES,
    })


@login_required
def delete_resource(request, pk):
    resource = get_object_or_404(Resource, pk=pk, owner=request.user)
    has_requests = resource.requests.exists()

    if request.method == 'POST':
        if has_requests:
            messages.error(
                request,
                "This item has requests, so it can't be deleted. Mark it unavailable instead.",
            )
        else:
            resource.delete()
            messages.success(request, "Listing deleted.")
        return redirect('my_listings')

    return render(request, 'resources/delete_resource.html', {
        'resource': resource,
        'has_requests': has_requests,
    })

@login_required
def browse(request):
    resources = (
        Resource.objects.filter(is_hidden=False, owner__is_active=True)
        .select_related('owner', 'category')
        .prefetch_related('images')
        .annotate(
            owner_rating=Avg('owner__reviews_received__rating'),
            owner_review_count=Count('owner__reviews_received', distinct=True),
        )
        .order_by('-created_at')
    )

    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    listing_type = request.GET.get('type', '')
    condition = request.GET.get('condition', '')
    availability = request.GET.get('availability', '')

    if q:
        resources = resources.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(category__name__icontains=q)
        )
    if category.isdigit():
        resources = resources.filter(category_id=category)
    if listing_type in dict(Resource.LISTING_TYPE_CHOICES):
        resources = resources.filter(listing_type=listing_type)
    if condition in dict(Resource.CONDITION_CHOICES):
        resources = resources.filter(condition=condition)
    if availability == 'available':
        resources = resources.filter(status='available')

    paginator = Paginator(resources, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)

    return render(request, 'resources/browse.html', {
        'page_obj': page_obj,
        'total': paginator.count,
        'categories': Category.objects.all(),
        'type_choices': Resource.LISTING_TYPE_CHOICES,
        'condition_choices': Resource.CONDITION_CHOICES,
        'filters': {
            'q': q,
            'category': category,
            'type': listing_type,
            'condition': condition,
            'availability': availability,
        },
        'querystring': params.urlencode(),
    })

@login_required
def resource_detail(request, pk):
    resource = get_object_or_404(
        Resource.objects.select_related('owner', 'category').prefetch_related('images'),
        pk=pk,
    )
    is_owner = resource.owner_id == request.user.id

    # Items hidden by an admin are visible only to their owner and to admins
    if (resource.is_hidden or not resource.owner.is_active) and not is_owner and not request.user.is_staff:
        raise Http404

    # Has this user already got a request in progress for this item?
    existing_request = None
    if not is_owner:
        existing_request = BorrowRequest.objects.filter(
            resource=resource, borrower=request.user, status__in=ACTIVE_STATUSES
        ).first()

    can_request = (
        not is_owner
        and resource.status == 'available'
        and not resource.is_hidden
        and existing_request is None
    )

    form = None
    show_modal = False

    if request.method == 'POST':
        if not can_request:
            messages.error(request, "This item can't be requested right now.")
            return redirect('resource_detail', pk=resource.pk)

        form = RequestForm(request.POST, resource=resource, borrower=request.user)
        if form.is_valid():
            new_request = form.save()
            who = request.user.first_name or "A student"
            Notification.objects.create(
                user=resource.owner,
                request=new_request,
                message=f'{who} requested "{resource.title}".',
            )
            messages.success(request, "Request sent! The owner has been notified.")
            return redirect('my_requests')
        show_modal = True          # errors: reopen the popup
    elif can_request:
        form = RequestForm(resource=resource, borrower=request.user)

    owner_reviews = Review.objects.filter(reviewee=resource.owner)
    stats = owner_reviews.aggregate(avg=Avg('rating'), count=Count('id'))
    recent_reviews = owner_reviews.select_related('reviewer').order_by('-created_at')[:5]

    return render(request, 'resources/resource_detail.html', {
        'resource': resource,
        'is_owner': is_owner,
        'can_request': can_request,
        'existing_request': existing_request,
        'form': form,
        'show_modal': show_modal,
        'owner_rating': stats['avg'],
        'owner_review_count': stats['count'],
        'reviews': recent_reviews,
    })