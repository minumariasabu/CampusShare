from django import forms
from django.contrib.auth.password_validation import validate_password
from .models import Institution, User
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import RegexValidator


class RegisterForm(forms.ModelForm):
    YEAR_CHOICES = [
        ('', 'Select year'),
        ('1st year', '1st year'),
        ('2nd year', '2nd year'),
        ('3rd year', '3rd year'),
        ('4th year', '4th year'),
        ('Other', 'Other'),
    ]

    year = forms.ChoiceField(choices=YEAR_CHOICES)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['first_name', 'email', 'department', 'year']
        labels = {
            'first_name': 'Full name',
            'email': 'College email',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['department'].required = True
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        institution = Institution.objects.first()
        if institution is None:
            raise forms.ValidationError("No institution is set up yet. Please contact the admin.")
        domain = email.split('@')[-1]
        if domain != institution.email_domain.lower():
            raise forms.ValidationError(
                f"Please use your college email (ending in @{institution.email_domain})."
            )
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2:
            if p1 != p2:
                self.add_error('password2', "The two passwords don't match.")
            else:
                try:
                    validate_password(p1)
                except forms.ValidationError as e:
                    self.add_error('password1', e)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = user.email          # we use the email as the login name
        user.set_password(self.cleaned_data['password1'])
        user.institution = Institution.objects.first()
        user.is_verified = False
        if commit:
            user.save()
        return user

class EmailLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="College email",
        widget=forms.TextInput(attrs={'autofocus': True, 'class': 'form-control'}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def clean_username(self):
        value = self.cleaned_data['username'].strip()
        if '@' in value:
            value = value.lower()
        return value

class ProfileForm(forms.ModelForm):
    year = forms.ChoiceField(choices=RegisterForm.YEAR_CHOICES)
    phone = forms.CharField(
        required=False,
        max_length=20,
        validators=[RegexValidator(r'^\+?[0-9 ]{7,15}$', "Enter a valid phone number (digits only).")],
    )

    class Meta:
        model = User
        fields = ['first_name', 'department', 'year', 'phone', 'photo']
        labels = {
            'first_name': 'Full name',
            'photo': 'Profile photo',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['department'].required = True
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            elif isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs['class'] = 'form-control'
                field.widget.attrs['accept'] = 'image/*'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean_phone(self):
        return self.cleaned_data['phone'].strip()

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if isinstance(photo, UploadedFile) and photo.size > 2 * 1024 * 1024:
            raise forms.ValidationError("The photo must be smaller than 2 MB.")
        return photo


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'