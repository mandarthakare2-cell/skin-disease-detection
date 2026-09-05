from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your username",
                "autocomplete": "username",
            }
        ),
    )
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
            }
        ),
    )


class RegistrationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Choose a username",
                "autocomplete": "username",
            }
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your email",
                "autocomplete": "email",
            }
        ),
    )
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Create a password",
                "autocomplete": "new-password",
            }
        ),
    )
    confirm_password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm your password",
                "autocomplete": "new-password",
            }
        ),
    )

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if len(username) < 3:
            raise ValidationError("Username must be at least 3 characters long.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already registered.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")

        if password and len(password) < 8:
            self.add_error("password", "Password must be at least 8 characters long.")

        return cleaned_data


class ImageUploadForm(forms.Form):
    image = forms.ImageField(
        widget=forms.ClearableFileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "class": "file-input",
            }
        )
    )

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            raise ValidationError("Please select an image to analyze.")

        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if getattr(image, "content_type", None) not in allowed_types:
            raise ValidationError("Unsupported file format. Use JPG, PNG, or WebP.")

        extension = image.name.lower().rsplit(".", 1)[-1] if "." in image.name else ""
        if extension not in {"jpg", "jpeg", "png", "webp"}:
            raise ValidationError("Unsupported file format. Use JPG, PNG, or WebP.")

        if image.size > 5 * 1024 * 1024:
            raise ValidationError("Image must be 5MB or smaller.")

        return image
