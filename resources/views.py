from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, render, redirect

from .forms import ResourceForm, ResourceEditForm
from .models import Resource, ResourceImage

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