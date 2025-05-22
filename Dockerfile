# --- Stage 1: бэктестинг и установка зависимостей ---
FROM python:3.10-slim AS base
# Устанавливаем системные зависимости, необходимые для сборки
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Копируем только зависимости для использования кэша Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: копирование кода и подготовка ---
FROM base AS build
COPY . .
# Собираем статику
RUN python manage.py collectstatic --noinput  # WhiteNoise автоматически обслужит статику после collectstatic :contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}
# Выполняем миграции
RUN python manage.py migrate --noinput

# --- Stage 3: финальный образ для продакшн-запуска ---
FROM base AS final
WORKDIR /app
COPY --from=build /app /app
ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=CourseMC.settings \
    PORT=8000
EXPOSE 8000
# Команда по умолчанию: запускаем Gunicorn на всех интерфейсах :contentReference[oaicite:2]{index=2}
CMD ["gunicorn", "CourseMC.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
