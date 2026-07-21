# API Документация (Swagger UI)

## 📚 Обзор

Проект теперь включает OpenAPI 3.0 документацию с Swagger UI для всех API endpoints.

## 🔐 Доступ к документации

API документация **защищена** и требует:
1. **Аутентификации** — войти через Keycloak
2. **Специального права** `inventory.view_api_docs`

**Важно**: Это право НЕ выдаётся автоматически группам "Наблюдатель". Доступ даётся только явно.

### Доступ через группу:

```bash
# Создать группу "API документация" с нужным правом
python manage.py bootstrap_roles

# Добавить пользователя в группу через админку или:
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from django.contrib.auth.models import Group
>>> user = User.objects.get(username='username')
>>> group = Group.objects.get(name='API документация')
>>> user.groups.add(group)
```
   - `inventory.access_inventory_app`
   - `contracts.access_contracts_app`
   - `access_monthly_report`
   - `dashboard.access_dashboard_app`
   - `view_okdesk_issues`
   - `access_supplies_report`

Без прав — 403 Forbidden.

## 🔗 Доступ к документации

После запуска сервера и авторизации:

- **Swagger UI**: http://localhost:8000/api/docs/
- **ReDoc**: http://localhost:8000/api/redoc/
- **OpenAPI Schema (JSON)**: http://localhost:8000/api/schema/

## 🚀 Установка

```bash
# Установить зависимости (требуется интернет)
pip install djangorestframework drf-spectacular

# Или через requirements.txt
pip install -r requirements.txt
```

## 📝 Документированные endpoints

### Printers (Принтеры)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v2/printers/` | Список принтеров с фильтрацией |
| GET | `/api/v2/printer/<id>/` | Детали принтера |
| GET | `/api/v2/all-printer-models/` | Все модели принтеров |
| GET | `/api/v2/printer/<id>/replacement-history/` | История замен |

### Inventory (Опрос)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v2/probe-serial/` | Опрос по serial number |
| POST | `/api/v2/printer/<id>/run/` | Запустить опрос |
| POST | `/api/v2/printer/<id>/poll/` | Синхронный опрос |

### System (Система)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v2/system-status/` | Статус системы |
| GET | `/api/v2/status-statistics/` | Статистика опросов |

## 🔐 Аутентификация

Все API endpoints требуют аутентификации через сессию Django.

В Swagger UI:
1. Нажмите кнопку **Authorize** 🔒
2. Введите свои credentials (через сессию браузера)

## 📊 Примеры запросов

### Получить список принтеров

```bash
curl -X GET "http://localhost:8000/api/v2/printers/?q_active=true&per_page=100" \
  -H "Cookie: sessionid=..."
```

### Запустить опрос принтера

```bash
curl -X POST "http://localhost:8000/api/v2/printer/123/run/" \
  -H "Cookie: sessionid=..."
```

## 🏷️ Теги

Endpoints организованы по тегам:
- `printers` — управление принтерами
- `inventory` — опрос устройств
- `system` — системное состояние

## 📦 Файлы

- `inventory/api_schemas.py` — схемы OpenAPI
- `inventory/api_views_drf.py` — DRF wrappers для документации
- `printer_inventory/settings.py` — настройки REST_FRAMEWORK и SPECTACULAR_SETTINGS
