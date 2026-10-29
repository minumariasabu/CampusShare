from django import forms

from resources.models import Category


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        same_name = Category.objects.filter(name__iexact=name)
        if self.instance.pk:
            same_name = same_name.exclude(pk=self.instance.pk)
        if same_name.exists():
            raise forms.ValidationError("A category with this name already exists.")
        return name