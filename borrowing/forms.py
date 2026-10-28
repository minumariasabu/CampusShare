from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Request, Review

# A request in any of these states is "still in progress"
ACTIVE_STATUSES = ['pending', 'approved', 'handed_over', 'return_initiated', 'overdue']


class RequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ['needed_from', 'return_by', 'message', 'exchange_offer']
        labels = {
            'needed_from': 'Needed from',
            'return_by': 'Return by',
            'message': 'Message to the owner',
            'exchange_offer': 'Item you are offering in exchange',
        }
        widgets = {
            'needed_from': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'return_by': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'message': forms.Textarea(attrs={'rows': 3}),
            'exchange_offer': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, resource, borrower, **kwargs):
        super().__init__(*args, **kwargs)
        self.resource = resource
        self.borrower = borrower

        # Show only the fields that make sense for this kind of listing
        if resource.listing_type == 'donate':
            del self.fields['return_by']
            del self.fields['exchange_offer']
        else:
            self.fields['return_by'].required = True
            self.fields['return_by'].help_text = (
                f"This item can be borrowed for at most {resource.max_borrow_days} day(s)."
            )
            if resource.listing_type == 'borrow':
                del self.fields['exchange_offer']

        today = timezone.localdate().isoformat()
        self.fields['needed_from'].widget.attrs['min'] = today
        if 'return_by' in self.fields:
            self.fields['return_by'].widget.attrs['min'] = today
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        resource = self.resource

        if resource.owner_id == self.borrower.id:
            raise ValidationError("You can't request your own item.")
        if resource.status != 'available' or resource.is_hidden:
            raise ValidationError("This item is not available right now.")
        if Request.objects.filter(
            resource=resource, borrower=self.borrower, status__in=ACTIVE_STATUSES
        ).exists():
            raise ValidationError("You already have an active request for this item.")

        needed_from = cleaned.get('needed_from')
        return_by = cleaned.get('return_by')

        if needed_from and needed_from < timezone.localdate():
            self.add_error('needed_from', "The date can't be in the past.")

        if 'return_by' in self.fields and needed_from and return_by:
            if return_by < needed_from:
                self.add_error('return_by', "The return date must be on or after the start date.")
            elif (return_by - needed_from).days > resource.max_borrow_days:
                self.add_error(
                    'return_by',
                    f"This item can be borrowed for at most {resource.max_borrow_days} day(s).",
                )

        if 'exchange_offer' in self.fields and not (cleaned.get('exchange_offer') or '').strip():
            self.add_error('exchange_offer', "Please describe the item you are offering.")

        return cleaned

    def save(self, commit=True):
        req = super().save(commit=False)
        req.resource = self.resource
        req.borrower = self.borrower
        req.request_type = self.resource.listing_type
        if commit:
            req.save()
        return req

class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[
            (5, '5 ★ Excellent'),
            (4, '4 ★ Good'),
            (3, '3 ★ Okay'),
            (2, '2 ★ Poor'),
            (1, '1 ★ Bad'),
        ],
        coerce=int,
        widget=forms.RadioSelect(attrs={'class': 'btn-check'}),
        error_messages={'required': 'Please choose a star rating.'},
    )
    comment = forms.CharField(
        required=False,
        max_length=500,
        label='Comment (optional)',
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment']

    def clean_comment(self):
        return self.cleaned_data['comment'].strip()