import logging

from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)

SALT = 'campusshare-verify-email'
MAX_AGE = 60 * 60 * 24 * 3          # links work for 3 days


def make_token(user):
    return signing.dumps({'uid': user.pk, 'email': user.email}, salt=SALT)


def read_token(token):
    return signing.loads(token, salt=SALT, max_age=MAX_AGE)


def send_verification_email(request, user):
    link = request.build_absolute_uri(reverse('verify_email', args=[make_token(user)]))
    name = user.first_name or 'there'
    body = (
        f"Hi {name},\n\n"
        "Welcome to CampusShare! Please confirm your college email by opening this link:\n\n"
        f"{link}\n\n"
        "The link works for 3 days. If you didn't create this account, you can ignore this email.\n"
    )
    try:
        send_mail('Verify your CampusShare account', body, None, [user.email])
        return True
    except Exception:
        logger.exception("Could not send verification email to user %s", user.pk)
        return False