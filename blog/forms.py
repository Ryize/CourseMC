from django.forms import ModelForm

from CourseMC.widgets import RichTextEditorWidget

from .models import Post


class PostForm(ModelForm):
    class Meta:
        model = Post
        fields = (
            "title",
            "description",
            "content",
            "image",
            "categories",
        )
        widgets = {"content": RichTextEditorWidget()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categories"].widget.attrs.update({"class": "form-control"})
        self.fields["image"].widget.attrs.update({"class": "form-control"})
