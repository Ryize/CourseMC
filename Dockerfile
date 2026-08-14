FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 1000 coursemc \
    && useradd --uid 1000 --gid coursemc --create-home coursemc

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

COPY --chown=coursemc:coursemc . /app

RUN mkdir -p /app/staticfiles /app/media /app/private_media \
    && chown -R coursemc:coursemc /app

USER coursemc

EXPOSE 8000

ENTRYPOINT ["/app/deploy/entrypoint.sh"]
CMD ["gunicorn", "CourseMC.wsgi:application", "--config", "/app/deploy/gunicorn.conf.py"]
