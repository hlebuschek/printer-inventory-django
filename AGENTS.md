# AGENTS.md — Printer Inventory Django

Django 5.2 + PostgreSQL + Redis + Celery + Channels(Daphne) + Keycloak/OIDC + Vue 3/Vite + Bootstrap 5.
6 приложений: `inventory`, `contracts`, `access`, `monthly_report`, `integrations`, `dashboard`.

> Глубокий контекст уже описан — читай при необходимости, не пересказывай:
> **`CLAUDE.md`** (архитектура, модели, workflow опроса, Celery Beat, права),
> `docs/CODEBASE_OVERVIEW.md`, `docs/QUICK_REFERENCE.md`, `README.md`, `docs/TROUBLESHOOTING_QUEUE.md`.

## Окружение и команды

Всегда используй venv проекта: `.venv/bin/python` (Python 3.12). Node — версия 18 (`.nvmrc`).

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8000          # WSGI, БЕЗ WebSockets
.venv/bin/python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application  # ASGI, С WebSockets
.venv/bin/python manage.py test                            # тесты (Django runner, pytest НЕ настроен)
.venv/bin/python manage.py test inventory                  # тесты одного приложения
.venv/bin/python manage.py makemigrations && .venv/bin/python manage.py migrate
.venv/bin/black .                                          # формат (line-length 120)
.venv/bin/flake8                                           # линтер (E501/E203/W503/E202 отключены — их чинит black)
cd frontend && npm run dev                                 # Vite HMR
cd frontend && npm run build                               # сборка фронта
```

После правок Python-кода: прогони `black .` + `flake8` + относящиеся тесты, ошибки чини сам.

## Запуск серверов (важно для этого проекта)

- Серверы блокирующие — запускай в фоне с логом и проверяй, что отвечают (общее правило — в глобальном AGENTS.md):
  `nohup .venv/bin/python manage.py runserver 127.0.0.1:8000 > /tmp/run.log 2>&1 &` →
  `sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/` (ждём 200).
- **Если задача про WebSocket** (`/ws/inventory/`, `/ws/monthly-report/...`) — обычный `runserver` НЕ годится, поднимай **Daphne** + проверь, что Redis запущен.
- Celery-воркеры: `./start_workers.sh` (3 очереди + beat). Для отладки одной задачи — обычный `celery -A printer_inventory worker`.

## Обязательные конвенции (не нарушать)

- **Бизнес-логика — в `services.py`, НЕ во views.** Точка входа опроса — `inventory/services.py::run_inventory_for_printer()`.
- **Views:** FBV для API-эндпоинтов, CBV для CRUD.
- **ORM:** всегда `select_related()` / `prefetch_related()` для связанных объектов — иначе N+1.
- **Шаблоны/фронт:** ассеты только через `{% vite_asset %}`, НЕ `{% static %}`. Chart.js требует явного `Chart.register(...)` и canvas в DOM до `renderChart()` (после `loading.value=false` + `await nextTick()`).
- **Стиль:** black + flake8, 120 символов, PEP 8.
- **Минимальные точные правки.** Не рефактори «заодно», не трогай несвязанный код.

## Подводные камни

- **`MonthlyReport.organization` — это CharField, НЕ FK** (совпадает с `Organization.name`). Не делай join как по внешнему ключу.
- `Printer.model_display` → `"{Manufacturer} {ModelName}"`; только модель — `p.device_model.name`.
- **Валидация счётчиков** (`inventory/utils.py::validate_against_history`): падение счётчика >10% или Kyocera-баг (опрос <24ч + скачок >5000 стр) → отклонение результата. Не «чини» это как баг — это защита.
- **Celery:** 3 очереди — `high_priority`, `low_priority`, `daemon` (конфиг `printer_inventory/celery.py`). При проблемах с очередью см. `docs/QUEUE_OVERFLOW_FIX.md`.
- **Redis DB:** 0=кэш, 1=сессии, 2=inventory, 3=broker.
- **Секреты:** в `.env` — НИКОГДА не коммить `.env` и не вставляй секреты в код/чат.
- **Миграции:** не редактируй уже применённые миграции; новые — через `makemigrations`.

## Где что лежит

- `printer_inventory/settings.py` — вся конфигурация, middleware, installed apps.
- `inventory/services.py`, `inventory/web_parser.py`, `inventory/utils.py` — движок опроса.
- `monthly_report/views.py` — самый большой view (~2800 строк), правь осторожно.
- `printer_inventory/auth_backends.py`, `auth_views.py` — OIDC/Keycloak.
- `integrations/tasks.py` — фоновые задачи GLPI/Okdesk.
- Логи: `logs/django.log`, `logs/errors.log`, `logs/celery.log`, `logs/keycloak_auth.log`.
