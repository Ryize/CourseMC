import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST


MAX_EDITOR_IMAGE_SIZE = 8 * 1024 * 1024
IMAGE_EXTENSIONS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "GIF": ".gif",
    "WEBP": ".webp",
}


def _error(message, *, status=400):
    return JsonResponse(
        {"success": False, "files": [], "message": message},
        status=status,
    )


@login_required
@require_POST
def rich_text_image_upload(request):
    """Принимает только проверенные растровые изображения для редактора."""

    uploaded_file = next(iter(request.FILES.values()), None)
    if uploaded_file is None:
        return _error("Выберите изображение для загрузки.")
    if uploaded_file.size > MAX_EDITOR_IMAGE_SIZE:
        return _error("Изображение должно быть не больше 8 МБ.")

    try:
        image = Image.open(uploaded_file)
        image.verify()
        extension = IMAGE_EXTENSIONS.get(image.format)
    except (UnidentifiedImageError, OSError, ValueError):
        return _error("Файл не является поддерживаемым изображением.")

    if extension is None:
        return _error("Поддерживаются JPG, PNG, GIF и WebP.")

    uploaded_file.seek(0)
    now = timezone.now()
    relative_path = Path(
        "uploads",
        "editor",
        str(now.year),
        f"{now.month:02d}",
        f"{uuid.uuid4().hex}{extension}",
    )
    saved_name = default_storage.save(relative_path.as_posix(), uploaded_file)
    file_url = default_storage.url(saved_name)
    return JsonResponse(
        {
            "success": True,
            "files": [file_url],
            "path": "",
            "baseurl": "",
            "message": "Изображение загружено.",
        },
    )
