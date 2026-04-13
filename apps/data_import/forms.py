from django import forms

from .models import ImportSession


class ImportUploadForm(forms.ModelForm):
    class Meta:
        model = ImportSession
        fields = ["mode", "file_format", "uploaded_file"]
        widgets = {
            "mode": forms.Select(attrs={"class": "form-select"}),
            "file_format": forms.Select(attrs={"class": "form-select"}),
            "uploaded_file": forms.FileInput(attrs={"class": "form-control"}),
        }

    def clean_uploaded_file(self):
        f = self.cleaned_data["uploaded_file"]
        file_format = self.cleaned_data.get("file_format")

        if file_format == ImportSession.FileFormat.XML:
            if not f.name.lower().endswith(".xml"):
                raise forms.ValidationError("Для формата XML требуется файл .xml")
        elif file_format == ImportSession.FileFormat.EXCEL:
            if not f.name.lower().endswith((".xlsx", ".xls")):
                raise forms.ValidationError("Для формата Excel требуется файл .xlsx или .xls")

        if f.size > 50 * 1024 * 1024:  # 50 MB
            raise forms.ValidationError("Максимальный размер файла — 50 МБ.")

        return f
