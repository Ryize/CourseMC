# Stage 1: install dependencies
FROM public.ecr.aws/docker/library/python:3.10-slim AS base
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      apt-utils \
      build-essential \
      libc6-dev \
      libffi-dev \
      python3-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: copy code, collect static, migrate
FROM base AS build
COPY . .

# Создаём папку для STATIC_ROOT
RUN mkdir -p /app/CourseMC/static

RUN python manage.py collectstatic --noinput && \
    python manage.py migrate --noinput

# Stage 3: финальный образ
FROM base AS final
WORKDIR /app
COPY --from=build /app /app
ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=CourseMC.settings
EXPOSE 8000
CMD ["gunicorn", "CourseMC.wsgi:application", "--bind", "0.0.0.0:8000", "--workee
rs", "3"]
