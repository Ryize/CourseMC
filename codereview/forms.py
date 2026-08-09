from urllib.parse import urlparse

from django import forms

from .models import ProjectCategories


class ProjectForReviewForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=ProjectCategories.objects.order_by("title"),
        label="Категория проекта",
    )
    github = forms.URLField(label="Ссылка на репозиторий")
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        max_length=2000,
    )

    def clean_github(self):
        github = self.cleaned_data["github"].strip().rstrip("/")
        parsed = urlparse(github)
        if parsed.hostname not in {"github.com", "www.github.com"}:
            raise forms.ValidationError("Укажите ссылку на репозиторий GitHub.")

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) != 2:
            raise forms.ValidationError(
                "Ссылка должна вести на корень репозитория GitHub."
            )

        owner, repository = path_parts
        repository = repository.removesuffix(".git")
        return f"https://github.com/{owner}/{repository}"

    @property
    def repository_name(self):
        github = self.cleaned_data["github"]
        return github.removeprefix("https://github.com/")
