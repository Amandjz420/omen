web: gunicorn omen.wsgi --bind 0.0.0.0:$PORT --workers 3 --timeout 120
worker: python manage.py run_ai_worker --loop --interval 3
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
