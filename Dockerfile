FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend .
RUN SECRET_KEY=build-only python manage.py collectstatic --noinput
RUN useradd -m app && mkdir -p /data/media && chown -R app /app /data
USER app
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz')" || exit 1
CMD ["sh","-c","python manage.py migrate --noinput && python manage.py createcachetable && exec gunicorn bantay.wsgi -b 0.0.0.0:${PORT:-8000} --workers 1 --timeout 60 --access-logfile -"]
