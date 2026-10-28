# BantayBarangay (Django templates + PostgreSQL)

One Django service. Pages are server-rendered from `backend/templates/`; CSS, JS, logo and Leaflet live in `backend/static/`.
Resident side: `/app/`. Official side: `/official/`. Django admin (superuser only): `/django-admin/`. Health check: `/healthz`.
The REST API under `/api/` is still there (not used by the pages); it can be removed later.

## Run locally (Windows Command Prompt)
From the project folder, run:

    setup.bat
    run.bat

Open http://127.0.0.1:8000. `run.bat` also runs migrations and creates the cache table each time it starts.

To load demo data, stop the server and run:

    cd backend
    venv\Scripts\python.exe manage.py seed --demo

Demo accounts use `DemoPass#2026x`; do not seed demo data in production.

To run tests from Command Prompt:

    cd backend
    venv\Scripts\python.exe manage.py test

PowerShell and macOS/Linux users can follow the equivalent virtual-environment steps manually: create and activate a Python 3 virtual environment, install `backend/requirements.txt`, set `DEBUG=1`, then run `python manage.py migrate`, `python manage.py createcachetable`, and `python manage.py runserver` from `backend/`.

## Folder map
    backend/templates/   base.html, home.html, new_report.html, detail.html, alerts.html, bulletin.html, legal.html,
                         auth/ (login, register, forgot), partials/ (badge, card, empty, errors), registration/, 400/403/404/500.html
    backend/static/      css/app.css, js/app.js, js/theme.js, img/, vendor/leaflet/
    backend/core/        models.py (database + rules), web.py (page views), web_urls.py, serializers.py (validation reused), context.py

## Deploy on Render
Create a Render Web Service using the repository's `Dockerfile` and attach a PostgreSQL database. Set `DEBUG=0`, a strong generated `SECRET_KEY`, the database connection string as `DATABASE_URL`, `DB_SSL=1`, and `SSL_REDIRECT=1`. Render's `RENDER_EXTERNAL_HOSTNAME` is used automatically for Django's allowed host and CSRF origin; set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` explicitly only if you use a custom domain. Docker build no longer needs Node. The container start command runs migrations, then Gunicorn.

Configure persistent storage mounted at `/data` for uploads; `MEDIA_ROOT=/data/media` is already set in the production example. Configure SMTP environment variables to send password-reset emails; otherwise Django uses its console email backend.
Rollback: Render → Deploys → redeploy an earlier commit; for database changes see `python manage.py migrate core <migration>`.
Back up first from Command Prompt: `pg_dump -Fc "%DATABASE_URL%" > backup.dump` (PowerShell: `pg_dump -Fc "$env:DATABASE_URL" > backup.dump`).
