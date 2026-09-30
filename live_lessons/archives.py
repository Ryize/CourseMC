"""Экспорт снимка чата вместе с копиями отправленных вложений."""

import re
import shutil
from tempfile import TemporaryFile
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from django.core.files import File


def archive_filename(message_id, original_name):
    # Сохраняем понятное имя, но никогда не переносим путь из имени загрузки в ZIP.
    basename = original_name.replace('\\', '/').rsplit('/', 1)[-1]
    basename = re.sub(r'[^\w.\- ]+', '_', basename, flags=re.UNICODE).strip('. ')[:100]
    return f'files/{message_id:08d}-{basename or "file"}'


def save_bundle(archive, transcript, chat_rows):
    """Пишет ZIP на диск без загрузки вложений целиком в память."""
    with TemporaryFile() as temporary:
        with ZipFile(temporary, 'w', compression=ZIP_STORED, allowZip64=True) as bundle:
            bundle.writestr('chat.txt', transcript, compress_type=ZIP_DEFLATED)
            inventory = ['Вложения чата', '']
            for item in chat_rows:
                attachment = getattr(item, 'attachment', None)
                if not attachment:
                    continue
                archive_name = archive_filename(item.pk, attachment.original_name)
                attachment.file.open('rb')
                try:
                    with bundle.open(archive_name, 'w', force_zip64=True) as destination:
                        shutil.copyfileobj(attachment.file, destination, length=1024 * 1024)
                finally:
                    attachment.file.close()
                inventory.append(f'{archive_name} — {attachment.original_name}')
            if len(inventory) > 2:
                bundle.writestr('files/список-файлов.txt', '\n'.join(inventory) + '\n',
                                compress_type=ZIP_DEFLATED)
        temporary.seek(0)
        archive.file.save('chat.zip', File(temporary, name='chat.zip'), save=True)
