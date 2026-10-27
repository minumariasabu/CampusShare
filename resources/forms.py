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