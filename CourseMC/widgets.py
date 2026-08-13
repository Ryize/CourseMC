from django import forms
from django.urls import reverse_lazy


class RichTextEditorWidget(forms.Textarea):
    """Современный self-hosted HTML-редактор без внешних CDN."""

    template_name = "django/forms/widgets/textarea.html"

    class Media:
        css = {"all": ("myadmins/vendor/jodit/jodit.min.css",)}
        js = (
            "myadmins/vendor/jodit/jodit.min.js",
            "myadmins/rich_text_editor_v4.js",
        )

    def __init__(self, attrs=None):
        default_attrs = {
            "class": "cm-rich-text-editor",
            "data-editor-upload-url": reverse_lazy("rich_text_image_upload"),
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)
