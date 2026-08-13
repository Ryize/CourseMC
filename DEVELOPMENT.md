# Локальная разработка

Проект проверен на Python 3.12.0 и Django 5.2 LTS.

## Подготовка окружения

```shell
python3.12 --version
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`requirements.in` содержит только прямые зависимости проекта.
`requirements.txt` фиксирует полное проверенное окружение вместе с
транзитивными зависимостями.

## Базовые проверки

```shell
python manage.py check
python -m pip check
```

Перед применением миграций проверьте план:

```shell
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

Не используйте `migrate --fake`. История миграций была восстановлена через
согласованные baseline-миграции; порядок работы с существующими базами описан
в `MIGRATIONS.md`.
