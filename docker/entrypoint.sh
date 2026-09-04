#!/bin/sh
set -eu

wait_for() {
    host="$1"; port="$2"; name="$3"
    until python -c "import socket; socket.create_connection(('$host', $port), timeout=2)" 2>/dev/null; do
        echo "waiting for $name ($host:$port)..."
        sleep 2
    done
}

wait_for "${DB_HOST:-db}" "${DB_PORT:-5432}" postgres
wait_for "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}" redis

case "$1" in
    web)
        python manage.py migrate --noinput
        python manage.py bootstrap_roles
        # Первичный суперпользователь для /admin (управление whitelist и настройками).
        # Создаётся один раз, если заданы DJANGO_SUPERUSER_USERNAME/PASSWORD в .env.docker
        if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
            python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
User = get_user_model()
username = os.environ['DJANGO_SUPERUSER_USERNAME']
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, os.environ.get('DJANGO_SUPERUSER_EMAIL', ''), os.environ['DJANGO_SUPERUSER_PASSWORD'])
    print(f'superuser {username} created')
else:
    print(f'superuser {username} already exists')
"
        fi
        # staticfiles лежит на shared-томе для nginx — обновляем при каждом старте
        python manage.py collectstatic --noinput
        exec python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application
        ;;
    worker)
        exec celery -A printer_inventory worker \
            --queues=high_priority,low_priority,daemon,exports \
            --loglevel=INFO \
            --max-tasks-per-child=200 \
            --hostname=worker_all@%h
        ;;
    beat)
        exec celery -A printer_inventory beat --loglevel=INFO
        ;;
    *)
        exec "$@"
        ;;
esac
