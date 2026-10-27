from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import ResourceForm
from .models import ResourceImage

MAX_IMAGES = 5


@login_required
def add_resource(request):
    image_error = None
    if request.method == 'POST':
        form = ResourceForm(request.POST)
        images = request.FILES.getlist('images')

        if len(images) > MAX_IMAGES:
            image_error = f"You can upload at most {MAX_IMAGES} photos."
        elif any(not img.content_type.startswith('image/') for img in images):
            image_error = "Only image files are allowed."

        if form.is_valid() and not image_error:
            resource = form.save(commit=False)
            resource.owner = request.user
            resource.save()
            for img in images:
                ResourceImage.objects.create(resource=resource, image=img)
            messages.success(request, "Your item has been listed!")
            return redirect('dashboard')
    else:
        form = ResourceForm()
    return render(request, 'resources/add_resource.html', {
        'form': form,
        'image_error': image_error,
        'max_images': MAX_IMAGES,
    })