from django import forms

from .models import Resource


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = [
            'title', 'description', 'category', 'condition',
            'listing_type', 'max_borrow_days', 'pickup_location',
        ]
        labels = {
            'listing_type': 'Listing type',
            'max_borrow_days': 'Maximum borrow days',
            'pickup_location': 'Pickup location',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = 'Select a category'
        self.fields['category'].required = True
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_max_borrow_days(self):
        days = self.cleaned_data['max_borrow_days']
        if days < 1 or days > 90:
            raise forms.ValidationError("Enter a number of days between 1 and 90.")
        return days

class ResourceEditForm(ResourceForm):
    available = forms.BooleanField(required=False, label="Available for requests")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['available'].widget.attrs['class'] = 'form-check-input'
        if self.instance.status == 'lent_out':
            self.fields['available'].disabled = True
            self.fields['available'].initial = False
            self.fields['available'].help_text = (
                "This item is currently lent out, so availability can't be changed."
            )
        else:
            self.fields['available'].initial = (self.instance.status == 'available')

    def save(self, commit=True):
        resource = super().save(commit=False)
        if resource.status != 'lent_out':
            resource.status = 'available' if self.cleaned_data['available'] else 'unavailable'
        if commit:
            resource.save()
        return resource