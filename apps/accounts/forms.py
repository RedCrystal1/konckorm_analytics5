from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UserChangeForm

from .models import User


class LoginForm(AuthenticationForm):
    """Форма входа в систему."""

    username = forms.CharField(
        label="Имя пользователя",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Введите логин", "autofocus": True}
        ),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "placeholder": "Введите пароль"}
        ),
    )


class UserCreateForm(UserCreationForm):
    """Форма создания пользователя (для администратора)."""

    class Meta:
        model = User
        fields = [
            "username",
            "last_name",
            "first_name",
            "patronymic",
            "email",
            "role",
            "department",
            "phone",
            "position",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "patronymic": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "position": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs["class"] = "form-control"
        self.fields["password2"].widget.attrs["class"] = "form-control"


class UserUpdateForm(UserChangeForm):
    """Форма редактирования пользователя (для администратора)."""

    password = None  # Убираем поле пароля

    class Meta:
        model = User
        fields = [
            "username",
            "last_name",
            "first_name",
            "patronymic",
            "email",
            "role",
            "department",
            "phone",
            "position",
            "is_active",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "patronymic": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "position": forms.TextInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ProfileForm(forms.ModelForm):
    """Форма редактирования профиля (для самого пользователя)."""

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "patronymic",
            "email",
            "phone",
            "position",
            "notify_overdue",
            "notify_cash_gap",
            "notify_import",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "patronymic": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "position": forms.TextInput(attrs={"class": "form-control"}),
            "notify_overdue": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notify_cash_gap": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notify_import": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
