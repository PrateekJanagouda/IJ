FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN useradd --create-home --uid 1000 eqora
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN DJANGO_DEBUG=true python manage.py collectstatic --noinput

USER eqora
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
