from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from borrowing.models import Notification, Request


def send_once(user, req, text):
    """Create a notification, unless the same one already exists."""
    text = text[:255]
    if Notification.objects.filter(user=user, request=req, message=text).exists():
        return False
    Notification.objects.create(user=user, request=req, message=text)
    return True


class Command(BaseCommand):
    help = "Marks late requests as overdue and sends return reminders."

    def handle(self, *args, **options):
        today = timezone.localdate()
        soon = today + timedelta(days=1)

        # Donations finish at handover, so only loans have a return date
        loans = (
            Request.objects.exclude(request_type='donate')
            .filter(return_by__isnull=False)
            .select_related('resource', 'resource__owner', 'borrower')
        )

        # 1. Late items become Overdue
        marked = 0
        for req in list(loans.filter(status='handed_over', return_by__lt=today)):
            changed = Request.objects.filter(
                pk=req.pk, status='handed_over'
            ).update(status='overdue')
            if not changed:
                continue
            marked += 1

            title = req.resource.title
            due = req.return_by.strftime('%d %b %Y')
            who = req.borrower.first_name or 'The borrower'
            send_once(
                req.borrower, req,
                f'Overdue: "{title}" was due back on {due}. Please return it as soon as possible.',
            )
            send_once(
                req.resource.owner, req,
                f'"{title}" is overdue. {who} was due to return it on {due}.',
            )

        # 2. Reminders for items due today or tomorrow
        reminders = 0
        for req in loans.filter(status='handed_over', return_by__gte=today, return_by__lte=soon):
            due = req.return_by.strftime('%d %b %Y')
            if send_once(
                req.borrower, req,
                f'Reminder: "{req.resource.title}" is due back on {due}.',
            ):
                reminders += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done: {marked} marked overdue, {reminders} reminders sent.'
        ))