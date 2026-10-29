from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.core import signing
from django.core.cache import cache

from .emails import read_token, send_verification_email
from resources.models import Resource
from .models import User

from borrowing.models import Review
from .forms import ProfileForm, RegisterForm, StyledPasswordChangeForm


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            request.session['verify_email'] = user.email
            if send_verification_email(request, user):
                messages.success(request, "Account created! We've sent you a verification link.")
            else:
                messages.warning(
                    request,
                    "Account created, but we couldn't send the email. Please use 'Resend' below.",
                )
            return redirect('verify_sent')
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

def verify_sent(request):
    return render(request, 'accounts/verify_sent.html', {
        'email': request.session.get('verify_email', ''),
    })


def verify_email(request, token):
    try:
        data = read_token(token)
    except signing.SignatureExpired:
        messages.error(request, "This verification link has expired. Please request a new one.")
        return redirect('verify_resend')
    except signing.BadSignature:
        messages.error(request, "This verification link is not valid.")
        return redirect('verify_resend')

    user = User.objects.filter(pk=data.get('uid'), email=data.get('email')).first()
    if user is None:
        messages.error(request, "This verification link is not valid.")
        return redirect('verify_resend')

    if not user.is_verified:
        user.is_verified = True
        user.save(update_fields=['is_verified'])
    messages.success(request, "Email verified! You can now log in.")
    return redirect('login')


def resend_verification(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()

        # At most one email per minute per account
        if user and not user.is_verified and not user.is_staff:
            if cache.add(f'verify-resend-{user.pk}', 1, 60):
                send_verification_email(request, user)

        request.session['verify_email'] = email
        messages.success(
            request,
            "If that address belongs to an unverified account, we've sent a new link.",
        )
        return redirect('verify_sent')

    return render(request, 'accounts/verify_resend.html', {
        'email': request.session.get('verify_email', ''),
    })