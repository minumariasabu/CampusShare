from django.core.management.base import BaseCommand

from accounts.models import Institution
from resources.models import Category

DEFAULT_CATEGORIES = [
    ('Books', 'Textbooks, notes and reference books'),
    ('Electronics', 'Calculators, chargers and gadgets'),
    ('Lab equipment', 'Lab coats, kits and tools'),
    ('Sports', 'Rackets, balls and gear'),
    ('Stationery', 'Drawing and writing supplies'),
]


class Command(BaseCommand):
    help = "Creates the college (Institution) and a few starter categories."

    def add_arguments(self, parser):
        parser.add_argument('--name', required=True, help='College name')
        parser.add_argument('--domain', required=True, help='Email domain, e.g. abccollege.edu.in')

    def handle(self, *args, **options):
        name = options['name'].strip()
        domain = options['domain'].strip().lower().lstrip('@')

        institution = Institution.objects.first()
        if institution:
            institution.name = name
            institution.email_domain = domain
            institution.save()
            self.stdout.write(f'Updated college: {name} (@{domain})')
        else:
            Institution.objects.create(name=name, email_domain=domain)
            self.stdout.write(f'Created college: {name} (@{domain})')

        for cat_name, description in DEFAULT_CATEGORIES:
            Category.objects.get_or_create(name=cat_name, defaults={'description': description})

        self.stdout.write(self.style.SUCCESS('Setup complete.'))