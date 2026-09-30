import codecs
import os

from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.urls import reverse


MAX_MESSAGE_LENGTH = 3000
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024

# Загруженное никогда не отдаётся из публичного /media/; расширение не является
# основанием доверять присланному MIME-типу, поэтому проверяем сигнатуру.
ATTACHMENT_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.txt': 'text/plain',
    '.md': 'text/plain',
    '.py': 'text/plain',
}


def is_utf8_text(upload):
    decoder = codecs.getincrementaldecoder('utf-8')()
    try:
        for chunk in upload.chunks():
            if b'\x00' in chunk:
                return False
            decoder.decode(chunk)
        decoder.decode(b'', final=True)
        return True
    except UnicodeDecodeError:
        return False
    finally:
        upload.seek(0)


def validate_attachment(upload):
    if upload.size == 0 or upload.size > MAX_ATTACHMENT_BYTES:
        raise ValidationError('Размер файла должен быть от 1 байта до 25 МБ.')
    original_name = os.path.basename(upload.name.replace('\\', '/'))
    extension = os.path.splitext(original_name)[1].lower()
    content_type = ATTACHMENT_TYPES.get(extension)
    if not content_type:
        raise ValidationError('Этот тип файла не поддерживается.')
    header = upload.read(512)
    upload.seek(0)
    if extension == '.png':
        valid = header.startswith(b'\x89PNG\r\n\x1a\n')
    elif extension in ('.jpg', '.jpeg'):
        valid = header.startswith(b'\xff\xd8\xff')
    elif extension == '.gif':
        valid = header.startswith((b'GIF87a', b'GIF89a'))
    elif extension == '.webp':
        valid = header.startswith(b'RIFF') and header[8:12] == b'WEBP'
    elif extension == '.mp4':
        valid = header[4:8] == b'ftyp'
    elif extension == '.webm':
        valid = header.startswith(b'\x1a\x45\xdf\xa3')
    elif extension == '.pdf':
        valid = header.startswith(b'%PDF-')
    elif extension in ('.docx', '.xlsx', '.pptx'):
        valid = header.startswith(b'PK\x03\x04')
    else:
        valid = is_utf8_text(upload)
    if not valid:
        if extension in ('.txt', '.md', '.py'):
            raise ValidationError('Текстовый файл должен быть в UTF-8 и не содержать бинарных данных.')
        raise ValidationError('Содержимое файла не соответствует его типу.')
    if content_type.startswith('image/'):
        try:
            with Image.open(upload) as image:
                if image.width * image.height > 20_000_000:
                    raise ValidationError('Изображение слишком большое по разрешению.')
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError):
            raise ValidationError('Изображение повреждено или имеет неверный формат.') from None
        finally:
            upload.seek(0)
    return original_name[-120:], content_type


def message_payload(message):
    attachment = getattr(message, 'attachment', None)
    author = message.author
    return {
        'id': message.pk,
        'author': (author.get_full_name().strip() or author.username) if author else message.guest_name,
        'author_id': message.author_id if author else f'guest:{message.guest_id.hex}',
        'body': message.body,
        'created_at': message.created_at.isoformat(),
        'attachment': {
            'name': attachment.original_name,
            'size': attachment.size,
            'url': reverse('live_lesson_chat_attachment', args=[
                message.lesson.public_id, attachment.pk,
            ]),
        } if attachment else None,
    }
