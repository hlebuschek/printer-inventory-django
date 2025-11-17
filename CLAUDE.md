# CLAUDE.md - Руководство для AI-ассистентов по Printer Inventory Django

**Последнее обновление:** 2025-11-17
**Назначение:** Комплексное руководство для AI-ассистентов, работающих с этой системой управления инвентаризацией принтеров на Django

---

## Краткий обзор проекта

**Что это?** Веб-приложение на Django для управления сетевыми принтерами с опросом по SNMP, веб-парсингом, обновлениями в реальном времени, управлением контрактами и формированием отчетов о соответствии.

**Технологический стек:** Django 5.2 + PostgreSQL + Redis + Celery + Django Channels + Keycloak/OIDC + Alpine.js + Bootstrap 5

**Размер:** ~8,000 строк Python-кода в 4 Django-приложениях

---

## Критически важные файлы и их расположение

### Конфигурация
- `printer_inventory/settings.py` (23KB) - Вся конфигурация Django, middleware, установленные приложения
- `.env` - Переменные окружения (DATABASE, REDIS, KEYCLOAK учетные данные)
- `docker-compose.yml` - Настройка Keycloak для разработки

### Основная бизнес-логика
- `inventory/services.py` (611 строк) - **ОСНОВНОЙ ДВИЖОК ОПРОСА** - Прочитайте это в первую очередь!
- `inventory/web_parser.py` (18KB) - Движок веб-скрейпинга (XPath + Regex)
- `monthly_report/services_inventory_sync.py` (16KB) - Логика синхронизации инвентаря
- `printer_inventory/auth_backends.py` (13KB) - Интеграция Keycloak/OIDC

### Модели (схема данных)
- `inventory/models.py` (377 строк) - Printer, InventoryTask, PageCounter, WebParsingRule
- `contracts/models.py` (10KB) - DeviceModel, ContractDevice, Cartridge
- `monthly_report/models.py` (311 строк) - MonthlyReport
- `access/models.py` - AllowedUser (белый список)

### Представления (модульные)
- `inventory/views/printer_views.py` - CRUD операции для принтеров
- `inventory/views/api_views.py` - REST API эндпоинты (17KB)
- `inventory/views/web_parser_views.py` - UI веб-парсинга (23KB)
- `inventory/views/export_views.py` - Экспорт в Excel (14KB)
- `contracts/views.py` (33KB) - Управление контрактами
- `monthly_report/views.py` (49KB) - Интерфейс отчетов

### Асинхронные задачи
- `inventory/tasks.py` - Задачи Celery для опроса
- `inventory/consumers.py` - WebSocket потребитель (Django Channels)
- `printer_inventory/celery.py` - Конфигурация приложения Celery

### Шаблоны и фронтенд
- `templates/base.html` - Главный макет с Alpine.js
- `static/js/vendor/alpine.min.js` - Реактивный фреймворк
- `static/css/vendor/bootstrap.min.css` - CSS фреймворк

---

## Архитектурные паттерны

### 1. Django приложения (модульный дизайн)
Каждое приложение самодостаточно с моделями, представлениями, формами, шаблонами, админкой, URL:
- **inventory** - Управление принтерами и опрос
- **contracts** - Отслеживание контрактов устройств
- **access** - Аутентификация и авторизация
- **monthly_report** - Отчеты о соответствии

### 2. Паттерн слоя сервисов
**Тяжелая бизнес-логика находится в файлах `services.py`, НЕ в представлениях.**
- Представления обрабатывают HTTP запросы/ответы
- Сервисы обрабатывают бизнес-логику
- Пример: `run_inventory_for_printer()` в `inventory/services.py`

### 3. Очередь задач (Celery)
Длительные операции используют задачи Celery:
- **3 очереди по приоритету:** high_priority, default, low_priority
- Запланированные задачи через Celery Beat
- Сохраняет отзывчивость UI

### 4. Стратегия кэширования (Redis)
**3 базы данных Redis:**
- DB 0: Общий кэш (TTL 15 мин)
- DB 1: Сессии (TTL 7 дней)
- DB 2: Данные инвентаря (TTL 30 мин)

### 5. Обновления в реальном времени (WebSockets)
- Django Channels + Redis pub/sub
- WebSocket эндпоинт: `/ws/inventory/`
- Отправляет обновления при завершении опросов

### 6. Обработка ошибок
- Пользовательские страницы ошибок (400, 403, 404, 405, 500)
- Готовое к production логирование в `logs/django.log` и `logs/errors.log`
- Middleware безопасности и защита CSRF

### 7. Аутентификация (корпоративный OIDC)
- Keycloak как провайдер идентификации
- Модель белого списка AllowedUser
- Пользовательский OIDC бэкенд с автоматическим обновлением токенов
- Разрешения на основе групп

---

## Иерархия моделей данных

```
Organization
  ├── Printer (IP адрес, SNMP community, метод опроса)
  │   ├── InventoryTask (история опросов со статусом)
  │   │   └── PageCounter (счетчики и расходники на каждый опрос)
  │   └── WebParsingRule (правила извлечения XPath/Regex)
  │       └── WebParsingTemplate (переиспользуемые конфигурации)
  │
  └── ContractDevice (устройство в управлении контрактами)
      ├── DeviceModel (производитель, характеристики, тип)
      │   ├── Manufacturer
      │   ├── Cartridge (расходники)
      │   └── ContractStatus
      └── OneToOne → Printer (связь с инвентарем)

MonthlyReport (синхронизировано из данных InventoryTask)
  └── Counters (начало/конец, флаги ручного редактирования, расчеты K1/K2)
```

---

## Основные рабочие процессы

### Рабочий процесс опроса (Самое важное!)
```
1. Триггер
   - Вручную: Пользователь нажимает кнопку "Запустить опрос"
   - Автоматически: Планировщик Celery Beat (каждые 60 мин по умолчанию)

2. Диспетчеризация задачи
   - Вручную → run_inventory_task_priority() [очередь high_priority]
   - По расписанию → run_inventory_task() [очередь low_priority]

3. Выполнение сервиса (inventory/services.py)
   run_inventory_for_printer(printer_id)
   ├── Если polling_method == SNMP:
   │   ├── Вызов GLPI Agent через subprocess
   │   ├── Парсинг XML ответа
   │   └── Извлечение счетчиков, расходников, серийного номера, MAC
   └── Если polling_method == WEB:
       ├── Получение веб-интерфейса принтера
       ├── Применение правил XPath/Regex (WebParsingRule)
       └── Извлечение счетчиков из HTML

4. Сохранение результатов
   - Создание InventoryTask (статус, метки времени, сообщения об ошибках)
   - Создание PageCounter (счетчики, расходники, уровни)
   - Связь с Printer

5. Уведомление клиентов
   - Отправка WebSocket сообщения группе 'inventory_updates'
   - Обновление UI в реальном времени без перезагрузки страницы

6. Синхронизация (опционально)
   - Приложение monthly_report синхронизирует счетчики при необходимости
```

### Рабочий процесс аутентификации
```
1. Пользователь посещает /accounts/login/
2. Выбор Keycloak (OIDC) или Django login
3. Если Keycloak:
   - Перенаправление на страницу входа Keycloak
   - Пользователь аутентифицируется
   - Callback на /oidc/callback/
   - CustomOIDCAuthenticationBackend.authenticate()
     └── Проверка AllowedUser.objects.filter(username=..., is_active=True)
     └── Создание или обновление Django User
4. Установка сессии в Redis (срок действия 7 дней)
5. Middleware автоматически обновляет токен перед истечением
6. Членство в группе определяет разрешения
```

### Рабочий процесс ежемесячной отчетности
```
1. Администратор импортирует Excel с данными оборудования
2. Создаются строки MonthlyReport (со счетчиками start_*)
3. Запускается команда синхронизации:
   - Получение последнего InventoryTask для каждого устройства
   - Обновление счетчиков end_* (с учетом флагов manual_edit_*)
4. Расчет метрик:
   - K1 = процент доступности
   - K2 = соответствие SLA
5. Экспорт в Excel для выставления счетов/соответствия
```

---

## Рабочие процессы разработки

### Добавление новой функции
```bash
1. Создание/изменение модели в apps/<app>/models.py
2. Генерация миграции: python manage.py makemigrations
3. Применение миграции: python manage.py migrate
4. Добавление представления в apps/<app>/views/ (или views.py)
5. Создание шаблона в templates/<app>/
6. Регистрация URL в apps/<app>/urls.py
7. Добавление интерфейса админки в apps/<app>/admin.py (опционально)
8. Написание тестов в apps/<app>/tests.py
9. Обновление этого CLAUDE.md при значительных изменениях
```

### Добавление API эндпоинта
```bash
1. Создание функции в inventory/views/api_views.py
2. Использование декоратора @require_http_methods(['GET', 'POST'])
3. Возврат JsonResponse() или использование декоратора @json_response
4. Регистрация в inventory/urls.py
5. Документирование в разделе API ниже
```

### Добавление задачи Celery
```bash
1. Создание @shared_task в apps/<app>/tasks.py
2. Импорт в printer_inventory/celery.py при необходимости
3. Для периодических: Добавление в CELERY_BEAT_SCHEDULE в settings.py
4. Тестирование: python manage.py shell
   >>> from inventory.tasks import my_task
   >>> my_task.delay(args)
5. Мониторинг: Проверка logs/celery.log
```

### Исправление ошибки
```bash
1. Проверка логов:
   - logs/django.log (общие ошибки)
   - logs/errors.log (production ошибки)
   - logs/celery.log (ошибки задач)
   - logs/keycloak_auth.log (проблемы аутентификации)

2. Воспроизведение в разработке:
   - python manage.py runserver
   - Добавление print() или logger.debug() выражений

3. Определение первопричины:
   - Проверка задействованного представления/сервиса
   - Просмотр последних git коммитов: git log --oneline

4. Написание тестового случая для предотвращения регрессии

5. Исправление и коммит с понятным сообщением
```

### Запуск тестов
```bash
# Все тесты
python manage.py test

# Конкретное приложение
python manage.py test inventory

# Конкретный тестовый класс
python manage.py test inventory.tests.TestPrinterModel

# Сохранение БД между запусками (быстрее)
python manage.py test --keepdb

# Подробный вывод
python manage.py test --verbosity=2
```

---

## Общие команды

### Разработка
```bash
# Веб-сервер (WSGI - простой, без WebSockets)
python manage.py runserver 0.0.0.0:8000

# ASGI сервер (WebSockets включены)
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application

# Celery worker (отдельный терминал)
celery -A printer_inventory worker --loglevel=info

# Celery beat планировщик (отдельный терминал)
celery -A printer_inventory beat --loglevel=info

# Или использование вспомогательного скрипта (production)
./start_workers.sh  # Запускает 3 worker + beat
```

### База данных
```bash
# Создание миграций после изменения моделей
python manage.py makemigrations

# Применение миграций
python manage.py migrate

# Создание пользователя-администратора
python manage.py createsuperuser

# Консоль базы данных
python manage.py dbshell

# Консоль Django
python manage.py shell
```

### Утилиты
```bash
# Переключение режима DEBUG
python manage.py toggle_debug --status
python manage.py toggle_debug --on
python manage.py toggle_debug --off

# Очистка старых задач опроса
python manage.py cleanup_old_tasks

# Импорт устаревшей БД Flask
python manage.py import_flask_db path/to/db.sqlite

# Управление белым списком
python manage.py manage_whitelist --add username
python manage.py manage_whitelist --list

# Мониторинг задач Celery
python manage.py celery_monitor

# Тестирование страниц ошибок
python manage.py test_errors --test-all

# Сбор статических файлов (production)
python manage.py collectstatic --noinput
```

---

## Ключевые соглашения и лучшие практики

### Стиль кода
- **Python:** PEP 8 (отступы 4 пробела)
- **Django:** Следование руководству по стилю Django
- **Длина строки:** максимум 120 символов (настроено в settings)
- **Импорты:** Группировка по порядку: stdlib, сторонние, Django, локальные
- **Комментарии:** Объясняйте ПОЧЕМУ, а не ЧТО (код должен быть самодокументированным)

### Соглашения Django
- Использование `select_related()` и `prefetch_related()` для избежания N+1 запросов
- Всегда добавляйте методы `__str__()` к моделям
- Использование `get_absolute_url()` для URL моделей
- Предпочтение представлений на основе классов для CRUD, функциональных представлений для API
- Использование форм Django для валидации
- Всегда устанавливайте `verbose_name` и `verbose_name_plural` в Meta модели

### Логирование
```python
import logging
logger = logging.getLogger(__name__)

# Использование соответствующих уровней
logger.debug("Подробная диагностическая информация")
logger.info("Общие информационные сообщения")
logger.warning("Предупреждающие сообщения")
logger.error("Сообщения об ошибках")
logger.exception("Исключение с traceback")  # Использовать в блоках except
```

### Обработка ошибок
```python
# В сервисах
try:
    result = risky_operation()
except SpecificException as e:
    logger.error(f"Не удалось выполнить X: {e}")
    return None, str(e)  # Возврат кортежа (результат, ошибка)

# В представлениях
try:
    data = service_function()
except Exception as e:
    messages.error(request, f"Операция не удалась: {e}")
    return redirect('some_view')
```

### Задачи Celery
```python
from celery import shared_task

@shared_task(bind=True, max_retries=3)
def my_task(self, arg):
    try:
        # Выполнение работы
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)  # Повтор через 60с
```

### WebSocket сообщения
```python
# Отправка обновления группе
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()
async_to_sync(channel_layer.group_send)(
    "inventory_updates",
    {
        "type": "inventory_update",
        "message": "Опрос завершен",
        "printer_id": printer.id,
    }
)
```

---

## API эндпоинты (приложение inventory)

### GET /inventory/api/printers/
Возвращает JSON список всех принтеров

### GET /inventory/api/printer/<id>/
Возвращает JSON детали конкретного принтера

### POST /inventory/api/run-poll/
Запуск опроса для принтера(ов)
- Тело: `{"printer_ids": [1, 2, 3]}`
- Возвращает: ID задач

### GET /inventory/api/task-status/<task_id>/
Получение статуса задачи Celery

### GET /inventory/api/latest-task/<printer_id>/
Получение последнего InventoryTask для принтера

### POST /inventory/api/web-parser/test/
Тестирование правил веб-парсинга
- Тело: `{"url": "...", "rules": [...]}`

### GET /inventory/export/excel/
Экспорт принтеров в Excel

### GET /inventory/export/amb/<org_id>/
Экспорт в формат AMB для организации

---

## URL паттерны (всего 62)

### Основные маршруты
- `/` - Главная страница (перенаправляет на inventory)
- `/admin/` - Админка Django (ограниченное использование, предпочтителен OIDC)
- `/accounts/login/` - Страница входа
- `/accounts/logout/` - Выход
- `/oidc/` - OIDC эндпоинты

### Маршруты инвентаря
- `/inventory/` - Список принтеров
- `/inventory/printer/<id>/` - Детали принтера
- `/inventory/printer/add/` - Добавить принтер
- `/inventory/printer/<id>/edit/` - Редактировать принтер
- `/inventory/printer/<id>/delete/` - Удалить принтер
- `/inventory/run-poll/` - Интерфейс массового опроса
- `/inventory/web-parser/` - Управление веб-парсингом
- `/inventory/api/...` - API эндпоинты (см. выше)

### Маршруты контрактов
- `/contracts/` - Список устройств по контрактам
- `/contracts/device/<id>/` - Детали устройства
- `/contracts/import/` - Импорт из Excel

### Маршруты ежемесячных отчетов
- `/monthly-report/` - Список отчетов
- `/monthly-report/<id>/` - Детали отчета
- `/monthly-report/sync/` - Синхронизация из инвентаря
- `/monthly-report/export/` - Экспорт в Excel

### Отладочные маршруты (только DEBUG=True)
- `/debug/errors/` - Меню тестирования ошибок

---

## Справочник переменных окружения

### Обязательные
```bash
SECRET_KEY=<случайная-строка-50-символов>
DEBUG=False
DB_NAME=printer_inventory
DB_USER=postgres
DB_PASSWORD=<надежный-пароль>
DB_HOST=localhost
DB_PORT=5432
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Аутентификация
```bash
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=printer-inventory
OIDC_CLIENT_ID=<из-keycloak>
OIDC_CLIENT_SECRET=<из-keycloak>
OIDC_VERIFY_SSL=True  # False только для разработки
```

### Сеть
```bash
ALLOWED_HOSTS=localhost,127.0.0.1,example.com
CSRF_TRUSTED_ORIGINS=http://localhost:8000,https://example.com
BASE_URL=http://localhost:8000
USE_HTTPS=False  # True для production
```

### GLPI Agent
```bash
GLPI_PATH=/usr/bin  # Linux: /usr/bin, Mac: /Applications/GLPI-Agent/bin
HTTP_CHECK=True  # Включить веб-парсинг
POLL_INTERVAL_MINUTES=60
```

### Опциональные
```bash
REDIS_PASSWORD=<если-установлен>
REDIS_DB=0
REDIS_SESSION_DB=1
REDIS_INVENTORY_DB=2
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

---

## Отладка и устранение неполадок

### Включение режима DEBUG
```bash
python manage.py toggle_debug --on
```
**ПРЕДУПРЕЖДЕНИЕ:** Никогда не включайте в production! Раскрывает конфиденциальные данные.

### Проверка логов
```bash
# Ошибки Django
tail -f logs/django.log

# Production ошибки
tail -f logs/errors.log

# Задачи Celery
tail -f logs/celery.log

# Проблемы аутентификации
tail -f logs/keycloak_auth.log
```

### Тестирование WebSockets
```javascript
// Консоль браузера
const ws = new WebSocket('ws://localhost:5000/ws/inventory/');
ws.onmessage = (e) => console.log('Получено:', JSON.parse(e.data));
ws.send(JSON.stringify({type: 'test', message: 'hello'}));
```

### Проверка Redis
```bash
redis-cli

# Проверка подключенных каналов
SMEMBERS inventory_updates

# Проверка кэшированных ключей
KEYS *

# Проверка сессии
KEYS "django.contrib.sessions*"
```

### Мониторинг Celery
```bash
# Активные задачи
celery -A printer_inventory inspect active

# Зарегистрированные задачи
celery -A printer_inventory inspect registered

# Статистика
celery -A printer_inventory inspect stats

# Или использование команды управления
python manage.py celery_monitor
```

### Запросы к базе данных
```python
# В консоли Django
from inventory.models import Printer

# Просмотр сгенерированного SQL
print(Printer.objects.filter(is_active=True).query)

# План выполнения запроса
print(Printer.objects.filter(is_active=True).explain())

# Подсчет запросов
from django.db import connection
print(len(connection.queries))
```

### Распространенные проблемы

**Проблема:** WebSockets не работают
**Решение:** Убедитесь, что запущен Daphne (не runserver), Redis доступен, проверьте путь `/ws/inventory/`

**Проблема:** Задачи Celery не выполняются
**Решение:** Убедитесь, что worker запущен, проверьте logs/celery.log, проверьте подключение к Redis

**Проблема:** Ошибка аутентификации OIDC
**Решение:** Проверьте, что Keycloak запущен, проверьте OIDC_CLIENT_ID/SECRET, проверьте logs/keycloak_auth.log

**Проблема:** Опрос не работает
**Решение:** Проверьте правильность GLPI_PATH, убедитесь в доступности IP принтера, проверьте правила файрвола

**Проблема:** Ошибки импорта после pull
**Решение:** `pip install -r requirements.txt`, запустите миграции, collectstatic

---

## Контрольный список безопасности

### Разработка
- [ ] DEBUG=True (только в разработке)
- [ ] OIDC_VERIFY_SSL=False (приемлемо для локального Keycloak)
- [ ] Слабый SECRET_KEY (приемлемо для разработки)

### Production
- [ ] DEBUG=False **КРИТИЧНО**
- [ ] Надежный SECRET_KEY (50+ случайных символов)
- [ ] ALLOWED_HOSTS настроен правильно
- [ ] CSRF_TRUSTED_ORIGINS настроен
- [ ] USE_HTTPS=True
- [ ] OIDC_VERIFY_SSL=True
- [ ] Надежный пароль базы данных
- [ ] Пароль Redis установлен (рекомендуется)
- [ ] Пользователи в белом списке в таблице AllowedUser
- [ ] Отключен ненужный доступ к админке Django
- [ ] SSL сертификаты настроены
- [ ] Разрешения директории логов (chmod 700)
- [ ] Страницы ошибок не раскрывают конфиденциальные данные
- [ ] Настроены регулярные резервные копии

---

## Оптимизация производительности

### База данных
```python
# Использование select_related для ForeignKey
printers = Printer.objects.select_related('organization').all()

# Использование prefetch_related для ManyToMany/обратных FK
devices = ContractDevice.objects.prefetch_related('device_model__cartridges').all()

# Добавление индексов базы данных
class Meta:
    indexes = [
        models.Index(fields=['created_at', 'status']),
    ]

# Использование only() для ограничения полей
printers = Printer.objects.only('id', 'hostname', 'ip_address')

# Использование defer() для исключения больших полей
printers = Printer.objects.defer('notes')
```

### Кэширование
```python
from django.core.cache import cache

# Кэширование дорогих запросов
def get_active_printers():
    key = 'active_printers_list'
    data = cache.get(key)
    if data is None:
        data = list(Printer.objects.filter(is_active=True))
        cache.set(key, data, 60 * 15)  # 15 минут
    return data

# Инвалидация при сохранении
from django.db.models.signals import post_save

@receiver(post_save, sender=Printer)
def invalidate_printer_cache(sender, instance, **kwargs):
    cache.delete('active_printers_list')
```

### Пагинация
```python
from django.core.paginator import Paginator

def printer_list(request):
    printers = Printer.objects.all()
    paginator = Paginator(printers, 50)  # 50 на страницу
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'template.html', {'page': page})
```

### Оптимизация Celery
```python
# Использование очередей по приоритету
@shared_task(queue='high_priority')
def urgent_task():
    pass

# Пакетные операции
@shared_task
def process_batch(item_ids):
    items = Item.objects.filter(id__in=item_ids)
    # Обработка пакетом
```

---

## Контрольный список развертывания

### Перед развертыванием
- [ ] Все тесты пройдены: `python manage.py test`
- [ ] Миграции созданы: `python manage.py makemigrations --check`
- [ ] Нет незавершенных миграций: `python manage.py migrate --plan`
- [ ] Статические файлы собраны: `python manage.py collectstatic`
- [ ] Переменные окружения настроены в .env
- [ ] SECRET_KEY обновлен
- [ ] DEBUG=False проверен

### Инфраструктура
- [ ] PostgreSQL установлен и настроен
- [ ] Redis установлен и настроен
- [ ] Realm Keycloak настроен
- [ ] SSL сертификаты установлены
- [ ] Nginx/Apache настроен как обратный прокси
- [ ] Правила файрвола настроены
- [ ] Стратегия резервного копирования готова

### Сервисы
- [ ] Daphne запущен: `python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application`
- [ ] Celery workers запущены: `./start_workers.sh`
- [ ] Celery beat запущен (для запланированных задач)
- [ ] Сервисы настроены на автоперезапуск (systemd)

### После развертывания
- [ ] Миграции запущены: `python manage.py migrate`
- [ ] Создан суперпользователь: `python manage.py createsuperuser`
- [ ] Добавлены начальные пользователи в белый список
- [ ] Протестирован процесс входа
- [ ] Протестирован опрос (ручной запуск)
- [ ] Проверены WebSocket соединения
- [ ] Проверены страницы ошибок (вызов 404, 500)
- [ ] Мониторинг логов на ошибки
- [ ] Настроена ротация логов
- [ ] Настроен мониторинг/оповещения

---

## Стратегия тестирования

### Unit тесты
```python
from django.test import TestCase
from inventory.models import Printer

class PrinterModelTest(TestCase):
    def setUp(self):
        self.printer = Printer.objects.create(
            hostname='test-printer',
            ip_address='192.168.1.100'
        )

    def test_printer_creation(self):
        self.assertEqual(self.printer.hostname, 'test-printer')

    def test_str_method(self):
        self.assertIn('test-printer', str(self.printer))
```

### Интеграционные тесты
```python
from django.test import Client, TestCase

class PrinterViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Создание тестового пользователя и вход

    def test_printer_list_view(self):
        response = self.client.get('/inventory/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'inventory/printer_list.html')
```

### Тесты задач Celery
```python
from inventory.tasks import run_inventory_task_priority

class TaskTest(TestCase):
    def test_polling_task(self):
        printer = Printer.objects.create(...)
        result = run_inventory_task_priority.apply(args=[printer.id])
        self.assertTrue(result.successful())
```

---

## Лучшие практики миграций

### Создание миграций
```bash
# Всегда проверяйте, что будет создано
python manage.py makemigrations --dry-run

# Создание миграции
python manage.py makemigrations

# Просмотр файла миграции перед применением!
cat inventory/migrations/0XXX_*.py

# Применение с предпросмотром плана
python manage.py migrate --plan

# Применение
python manage.py migrate
```

### Миграции данных
```python
# Создание пустой миграции
python manage.py makemigrations --empty inventory

# Редактирование файла миграции
from django.db import migrations

def populate_data(apps, schema_editor):
    Printer = apps.get_model('inventory', 'Printer')
    # Заполнение данных

def reverse_data(apps, schema_editor):
    # Обратная операция

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0XXX_previous'),
    ]

    operations = [
        migrations.RunPython(populate_data, reverse_data),
    ]
```

### Откат
```bash
# Откат последней миграции
python manage.py migrate inventory 0XXX_previous_migration

# Откат всех миграций для приложения
python manage.py migrate inventory zero
```

---

## Git рабочий процесс

### Стратегия веток
- **main** - Готовый к production код
- **claude/claude-md-mi2q74wa992fojfo-012g2tXZiXDou9JDBK88v3tX** - Текущая ветка функций (разрабатывайте здесь!)

### Сообщения коммитов
```
# Хорошие сообщения коммитов
Добавлена поддержка веб-парсинга для принтеров HP
Fix: Устранена проблема таймаута опроса (#123)
Refactor: Извлечена логика SNMP в слой сервисов
Update: Увеличен TTL кэша для данных инвентаря

# Плохие сообщения коммитов
исправлена ошибка
обновление
WIP
asdf
```

### Рабочий процесс Pull Request
```bash
# Убедитесь, что вы на правильной ветке
git checkout claude/claude-md-mi2q74wa992fojfo-012g2tXZiXDou9JDBK88v3tX

# Внесите изменения, закоммитьте
git add .
git commit -m "Добавлена функция X"

# Push (КРИТИЧНО: используйте флаг -u для первого push)
git push -u origin claude/claude-md-mi2q74wa992fojfo-012g2tXZiXDou9JDBK88v3tX

# Создание PR через UI GitHub или gh CLI
gh pr create --title "Функция X" --body "Описание..."
```

---

## Типичные задачи для AI-ассистентов

### Задача: Добавить новый атрибут принтера
1. Добавить поле в модель `Printer` в `inventory/models.py`
2. Запустить `python manage.py makemigrations`
3. Просмотреть миграцию, затем `python manage.py migrate`
4. Добавить поле в `PrinterForm` в `inventory/forms.py`
5. Обновить шаблон для отображения поля
6. Обновить админку при необходимости
7. Написать тест

### Задача: Добавить новый API эндпоинт
1. Добавить функцию в `inventory/views/api_views.py`
2. Добавить URL паттерн в `inventory/urls.py`
3. Протестировать с curl или Postman
4. Задокументировать в этом файле (раздел API)
5. Написать тест

### Задача: Исправить ошибку опроса
1. Проверить `logs/celery.log` на ошибки задач
2. Добавить логирование в `inventory/services.py`
3. Протестировать на одном принтере: запустить ручной опрос
4. Исправить проблему
5. Проверить на нескольких принтерах
6. Обновить обработку ошибок при необходимости
7. Закоммитить с префиксом "Fix:"

### Задача: Оптимизировать медленный запрос
1. Включить логирование запросов в settings (DEBUG=True временно)
2. Определить медленные запросы
3. Добавить `select_related()` или `prefetch_related()`
4. Добавить индексы базы данных при необходимости
5. Протестировать улучшение производительности
6. Закоммитить с префиксом "Optimize:"

### Задача: Добавить запланированную задачу
1. Создать задачу в `inventory/tasks.py`
2. Добавить в `CELERY_BEAT_SCHEDULE` в `settings.py`
3. Протестировать: `celery -A printer_inventory beat --loglevel=debug`
4. Проверить выполнение задачи в правильном интервале
5. Проверить логи
6. Закоммитить

---

## Дополнительные ресурсы

### Документация
- Django: https://docs.djangoproject.com/
- Celery: https://docs.celeryproject.org/
- Django Channels: https://channels.readthedocs.io/
- Keycloak: https://www.keycloak.org/documentation
- Alpine.js: https://alpinejs.dev/
- Bootstrap 5: https://getbootstrap.com/docs/5.0/

### Документация проекта
- `/docs/CODEBASE_OVERVIEW.md` - Подробная структура кодовой базы
- `/docs/QUICK_REFERENCE.md` - Краткая справка
- `/docs/ERROR_HANDLING.md` - Документация по обработке ошибок
- `/README.md` - Установка и настройка

### Полезные команды
```bash
# Просмотр истории git
git log --oneline | head -20
git log --graph --online --all

# Поиск конкретного коммита
git log --grep="polling"
git log --author="username"

# Просмотр истории файла
git log --follow -- inventory/services.py

# Blame (кто что изменил)
git blame inventory/services.py

# Поиск в кодовой базе
grep -r "function_name" .
grep -r "TODO" . --exclude-dir=venv
```

---

## Заметки для AI-ассистентов

### При начале задачи
1. **Сначала прочитайте соответствующие файлы** - Не делайте предположений
2. **Проверьте последние коммиты** - Поймите недавние изменения
3. **Просмотрите существующие паттерны** - Следуйте установленным соглашениям
4. **Планируйте перед кодированием** - Разбейте сложные задачи
5. **Запрашивайте уточнения** - Если требования неясны

### Рекомендации по модификации кода
1. **ВСЕГДА читайте файлы перед редактированием** - Сначала используйте инструмент Read
2. **Сохраняйте существующие паттерны** - Не вводите новые паттерны без причины
3. **Обновляйте связанные файлы** - Формы, админка, шаблоны, тесты
4. **Тестируйте изменения** - Запускайте тесты перед коммитом
5. **Документируйте значительные изменения** - Обновляйте этот CLAUDE.md при необходимости

### Распространенные ловушки, которых следует избегать
- Не изменяйте файлы `migrations/` напрямую (всегда используйте makemigrations)
- Не хардкодьте конфиденциальные данные (используйте переменные окружения)
- Не пропускайте обработку ошибок (оборачивайте рискованные операции в try/except)
- Не забывайте обновлять тесты при изменении кода
- Не коммитьте с DEBUG=True
- Не используйте синхронный код в задачах Celery для запросов к БД (используйте .objects.select_for_update())
- Не забывайте инвалидировать кэш при изменении данных

### Лучшие практики
- Используйте описательные имена переменных
- Держите функции сфокусированными (единственная ответственность)
- Добавляйте docstrings к сложным функциям
- Используйте подсказки типов, где это полезно
- Логируйте важные операции
- Обрабатывайте граничные случаи
- Пишите тесты для новых функций
- Делайте атомарные коммиты (одно логическое изменение на коммит)

---

**Последнее обновление:** 2025-11-17
**Сопровождающий:** AI Assistant
**Статус:** Активная разработка

Этот документ должен обновляться при внесении значительных изменений в архитектуру кодовой базы, рабочие процессы или соглашения.
