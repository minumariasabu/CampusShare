from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from resources.models import Resource
from .models import User

from borrowing.models import Review
from .forms import ProfileForm, RegisterForm, StyledPasswordChangeForm


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created! Please log in.")
            return redirect('login')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def my_profile(request):
    reviews_qs = Review.objects.filter(reviewee=request.user)
    stats = reviews_qs.aggregate(avg=Avg('rating'), count=Count('id'))
    reviews = (
        reviews_qs.select_related('reviewer', 'request__resource')
        .order_by('-created_at')[:10]
    )
    return render(request, 'accounts/my_profile.html', {
        'profile': request.user,
        'rating': stats['avg'],
        'review_count': stats['count'],
        'reviews': reviews,
    })


@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect('my_profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'accounts/edit_profile.html', {'form': form})


class ChangePasswordView(SuccessMessageMixin, PasswordChangeView):
    form_class = StyledPasswordChangeForm
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('my_profile')
    success_message = "Your password has been changed."

@login_required
def public_profile(request, pk):
    if pk == request.user.pk:
        return redirect('my_profile')

    profile = get_object_or_404(User.objects.select_related('institution'), pk=pk, is_active=True)

    reviews_qs = Review.objects.filter(reviewee=profile)
    stats = reviews_qs.aggregate(avg=Avg('rating'), count=Count('id'))
    reviews = (
        reviews_qs.select_related('reviewer', 'request__resource')
        .order_by('-created_at')[:10]
    )
    listings = (
        Resource.objects.filter(owner=profile, is_hidden=False, status='available')
        .prefetch_related('images')
        .order_by('-created_at')
    )

    return render(request, 'accounts/public_profile.html', {
        'profile': profile,
        'rating': stats['avg'],
        'review_count': stats['count'],
        'reviews': reviews,
        'listings': listings,
    })