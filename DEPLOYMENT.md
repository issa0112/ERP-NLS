# Deployment Guide

## 1) Set environment variables

Use the values from `.env.example` and set them on your hosting platform.

Required:
- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY=<long-random-secret>`
- `DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com`

If you use PostgreSQL:
- `DATABASE_URL=postgresql://user:password@host:5432/dbname`

## 2) Install dependencies

```bash
pip install django gunicorn psycopg[binary]
```

## 3) Run database and static commands

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
```

## 4) Run app server (example)

```bash
gunicorn nouvelle_logistique.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

## 5) Reverse proxy

Use Nginx/Caddy/Traefik in front of Gunicorn.
Make sure it forwards `X-Forwarded-Proto=https` so Django can enforce HTTPS correctly.
