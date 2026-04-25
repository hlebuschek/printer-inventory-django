# CLAUDE.md - Руководство для AI-ассистентов по Printer Inventory Django

**Последнее обновление:** 2026-04-23
**Назначение:** Комплексное руководство для AI-ассистентов, работающих с этой системой управления инвентаризацией принтеров на Django

---

## Краткий обзор проекта

**Что это?** Веб-приложение на Django для управления сетевыми принтерами с опросом по SNMP, веб-парсингом, обновлениями в реальном времени, управлением контрактами, интеграциями с GLPI/Okdesk, аналитическим дашбордом и формированием отчетов о соответствии.

**Технологический стек:** Django 5.2 + PostgreSQL + Redis + Celery + Django Channels + Keycloak/OIDC + Vue 3 + Vite + Bootstrap 5

**Размер:** ~15,000 строк Python-кода в 6 Django-приложениях + ~50 Vue-компонентов

---

## Критически важные файлы и их расположение

### Конфигурация
- `printer_inventory/settings.py` (670 строк) - Вся конфигурация Django, middleware, установленные приложения
- `.env` - Переменные окружения (DATABASE, REDIS, KEYCLOAK учетные данные)
- `docker-compose.yml` - Настройка Keycloak для разработки

### Основная бизнес-логика
- `inventory/services.py` (1129 строк) - **ОСНОВНОЙ ДВИЖОК ОПРОСА** - Прочитайте это в первую очередь!
- `inventory/web_parser.py` (507 строк) - Движок веб-скрейпинга (XPath + Regex)
- `monthly_report/services_inventory_sync.py` (382 строки) - Логика синхронизации инвентаря
- `printer_inventory/auth_backends.py` (240 строк) - Интеграция Keycloak/OIDC
- `printer_inventory/auth_views.py` (334 строки) - Кастомные auth views (login, logout, OIDC callback)
- `integrations/tasks.py` (567 строк) - Фоновые задачи GLPI/Okdesk интеграций

### Модели (схема данных)
- `inventory/models.py` (416 строк) - Printer, InventoryTask, PageCounter, WebParsingRule, WebParsingTemplate, PrinterChangeLog
- `contracts/models.py` (234 строки) - City, Manufacturer, DeviceModel, Cartridge, DeviceModelCartridge, ContractDevice, ContractStatus
- `monthly_report/models.py` (343 строки) - MonthlyReport, MonthControl, CounterChangeLog, BulkChangeLog
- `access/models.py` (189 строк) - AllowedUser, UserThemePreference, UserProfile, UserOkdeskToken, EntityChangeLog
- `integrations/models.py` (278 строк) - GLPISync, IntegrationLog, GLPICrossCheck, OkdeskIssue
- `dashboard/models.py` (15 строк) - DashboardAccess (proxy для прав)

### Представления (модульные)
- `inventory/views/printer_views.py` (423 строки) - CRUD операции для принтеров
- `inventory/views/api_views.py` (591 строка) - REST API эндпоинты
- `inventory/views/web_parser_views.py` (810 строк) - UI веб-парсинга
- `inventory/views/export_views.py` (341 строка) - Экспорт в Excel
- `contracts/views.py` (877 строк) - Управление контрактами
- `contracts/api_views.py` (685 строк) - API для Vue.js контрактов
- `monthly_report/views.py` (2815 строк) - Интерфейс отчетов
- `integrations/views.py` (505 строк) - GLPI и Okdesk API
- `dashboard/views/api_views.py` (382 строки) - Аналитические API дашборда
- `access/views.py` (176 строк) - Темы, токены, права

### Асинхронные задачи и WebSocket
- `inventory/tasks.py` - Задачи Celery для опроса (5 задач)
- `integrations/tasks.py` - Задачи GLPI/Okdesk (5 задач)
- `inventory/consumers.py` - WebSocket потребитель для опроса принтеров
- `inventory/routing.py` - WebSocket: `/ws/inventory/`
- `monthly_report/consumers.py` - WebSocket потребитель для real-time редактирования
- `monthly_report/routing.py` - WebSocket: `/ws/monthly-report/<year>/<month>/`
- `printer_inventory/celery.py` - Конфигурация приложения Celery
- `printer_inventory/asgi.py` - ASGI конфигурация с WebSocket поддержкой

### Фронтенд (Vue 3 + Vite)
- `frontend/vite.config.js` - Конфигурация Vite
- `frontend/src/main.js` - Точка входа Vue
- `frontend/src/components/` - Vue-компоненты (7 директорий)
- `frontend/src/composables/` - Vue composables (10 файлов)
- `frontend/src/stores/` - Pinia/state stores
- `frontend/src/utils/api.js` - HTTP утилиты
- `templates/base.html` - Главный макет
- Шаблоны используют `{% vite_asset %}` и `{% vite_css %}` (НЕ `{% static %}`) для Vite-сборок

### Нагрузочное тестирование (Locust)
- `tests/locust/locustfile.py` - Сценарии нагрузки (3 типа пользователей)
- `tests/locust/tasks/` - Модули задач (auth, inventory, contracts, api, reports)
- `tests/locust/locust.conf` - Конфигурация
- `tests/locust/setup_test_users.py` - Создание тестовых пользователей

---

## Архитектурные паттерны

### 1. Django приложения (модульный дизайн)
Каждое приложение самодостаточно с моделями, представлениями, формами, шаблонами, админкой, URL:
- **inventory** - Управление принтерами и опрос (SNMP + Web)
- **contracts** - Отслеживание контрактов устройств
- **access** - Аутентификация, авторизация, темы, профили
- **monthly_report** - Ежемесячные отчеты о соответствии
- **integrations** - Интеграции с GLPI и Okdesk
- **dashboard** - Аналитический дашборд с виджетами

### 2. Паттерн слоя сервисов
**Тяжелая бизнес-логика находится в файлах `services.py`, НЕ в представлениях.**
- Представления обрабатывают HTTP запросы/ответы
- Сервисы обрабатывают бизнес-логику
- Пример: `run_inventory_for_printer()` в `inventory/services.py`

### 3. Очередь задач (Celery)
Длительные операции используют задачи Celery:
- **3 очереди:** high_priority, low_priority, daemon
- 9 запланированных задач через Celery Beat
- Сохраняет отзывчивость UI

### 4. Стратегия кэширования (Redis)
**4 базы данных Redis** (на основе REDIS_DB):
- DB 0: Общий кэш (TTL 15 мин)
- DB 1: Сессии (TTL 7 дней)
- DB 2: Данные инвентаря (TTL 30 мин)
- DB 3: Celery брокер

### 5. Обновления в реальном времени (WebSockets)
- Django Channels + Redis pub/sub
- `/ws/inventory/` - обновления при завершении опросов
- `/ws/monthly-report/<year>/<month>/` - real-time совместное редактирование отчетов

### 6. Фронтенд (Vue 3 + Vite)
- **Vue 3** с Composition API (заменил Alpine.js)
- **Vite** для HMR в разработке и продакшн-сборки
- **Composables** для переиспользуемой логики (useUrlFilters, useWebSocket, useToast, useColumnVisibility и др.)
- **Chart.js 4** для графиков (требует явной регистрации `Chart.register(...)`)
- Темная/светлая тема с синхронизацией через API (`access/views.py:theme_preference_api`)

### 7. Обработка ошибок
- Пользовательские страницы ошибок (400, 403, 404, 405, 500)
- Готовое к production логирование в `logs/django.log` и `logs/errors.log`
- Middleware: SecurityHeadersMiddleware, AjaxSessionRefreshMiddleware, ErrorHandlingMiddleware, RequestLoggingMiddleware

### 8. Аутентификация (корпоративный OIDC)
- Keycloak как провайдер идентификации
- Модель белого списка AllowedUser
- Пользовательский OIDC бэкенд с автоматическим обновлением токенов
- Автоматический редирект на Keycloak для неавторизованных
- CustomOIDCCallbackView для обработки callback
- Heartbeat API для поддержания сессии
- AjaxSessionRefreshMiddleware для OIDC refresh в AJAX-запросах
- Разрешения на основе групп

### 9. Кастомные права доступа

**Inventory:**
- `access_inventory_app` - Доступ к модулю инвентаризации
- `run_inventory` - Запуск опроса одного принтера
- `export_printers` - Экспорт списка принтеров в Excel
- `export_amb_report` - Экспорт отчета для АМБ
- `manage_web_parsing` - Управление правилами веб-парсинга
- `view_web_parsing` - Просмотр правил веб-парсинга
- `can_create_public_templates` - Создание публичных шаблонов парсинга

**Contracts:**
- `access_contracts_app` - Доступ к модулю договоров
- `export_contracts` - Экспорт договоров в Excel

**Monthly Report:**
- `access_monthly_report` - Доступ к модулю ежемесячных отчетов
- `upload_monthly_report` - Загрузка отчетов из Excel
- `edit_counters_start` - Редактирование счетчиков на начало периода
- `edit_counters_end` - Редактирование счетчиков на конец периода
- `sync_from_inventory` - Синхронизация данных из Inventory
- `view_change_history` - Просмотр истории изменений
- `view_monthly_report_metrics` - Просмотр метрик автозаполнения и пользователей
- `can_manage_month_visibility` - Управление видимостью месяцев (публикация/скрытие)
- `can_reset_auto_polling` - Возврат принтера на автоопрос
- `can_poll_all_printers` - Опрос всех принтеров одновременно
- `can_delete_month` - Удаление месяца и всех связанных данных
- `override_auto_lock` - Игнорировать автоблокировку редактирования

**Dashboard:**
- `access_dashboard_app` - Доступ к дашборду

**Integrations (OkdeskIssue):**
- `view_okdesk_issues` - Просмотр заявок Okdesk
- `create_okdesk_issue` - Создание заявок в Okdesk
- `manage_okdesk_token` - Управление токеном Okdesk

**Access:**
- `view_entity_changes` - Просмотр истории изменений любой сущности

**Группы прав (создаются через `python manage.py bootstrap_roles`):**
- Ежемесячные отчёты — Просмотр / Загрузка / Редакторы / Синхронизация / Менеджеры / История
- Управление видимостью / Сброс автоопроса / Опрос всех принтеров

---

## Иерархия моделей данных

```
Organization
  ├── Printer (IP адрес, SNMP community, метод опроса, web credentials)
  │   ├── InventoryTask (история опросов со статусом)
  │   │   └── PageCounter (счетчики и расходники на каждый опрос)
  │   ├── WebParsingRule (правила извлечения XPath/Regex)
  │   │   └── WebParsingTemplate (переиспользуемые конфигурации)
  │   └── PrinterChangeLog (история изменений принтера)
  │
  └── ContractDevice (устройство в управлении контрактами)
      ├── DeviceModel (производитель, характеристики, тип, has_network_port)
      │   ├── Manufacturer
      │   ├── City
      │   ├── Cartridge (расходники)
      │   │   └── DeviceModelCartridge (M2M с is_primary, comment)
      │   └── ContractStatus
      └── OneToOne → Printer (связь с инвентарем)

MonthlyReport (синхронизировано из данных InventoryTask)
  ├── Counters (начало/конец, флаги ручного редактирования, расчеты K1/K2)
  ├── MonthControl (настройки месяца: edit_until, is_published)
  ├── CounterChangeLog (история изменений счетчиков)
  └── BulkChangeLog (массовые изменения)

Integrations
  ├── GLPISync (логи синхронизации с GLPI)
  ├── IntegrationLog (общие логи интеграций)
  ├── GLPICrossCheck (кросс-проверка устройств в GLPI)
  └── OkdeskIssue (заявки Okdesk с привязкой к серийным номерам)

Access
  ├── AllowedUser (белый список Keycloak)
  ├── UserThemePreference (тема: light/dark/system)
  ├── UserProfile (доп. данные: телефон)
  ├── UserOkdeskToken (зашифрованные токены Okdesk)
  └── EntityChangeLog (универсальная история изменений)
```

---

## Основные рабочие процессы

### Рабочий процесс опроса (Самое важное!)
```
1. Триггер
   - Вручную: Пользователь нажимает кнопку "Запустить опрос"
   - Автоматически: inventory_daemon_task через Celery Beat (каждый час в XX:00)
   - Очистка очереди: cleanup_queue_if_needed (XX:55, за 5 мин до daemon)

2. Диспетчеризация задачи
   - Вручную → run_inventory_task_priority() [очередь high_priority]
   - По расписанию → inventory_daemon_task() [очередь daemon]

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

4. Валидация данных (inventory/utils.py:validate_against_history)
   - Проверка соответствия исторических паттернов (A3, цвет)
   - Проверка на уменьшение счетчиков (> 10%)
   - ЗАЩИТА ОТ АНОМАЛЬНЫХ СКАЧКОВ (Kyocera bug):
     - Если последний опрос < 24ч и скачок > 5,000 стр → HISTORICAL_INCONSISTENCY
     - Если последний опрос > 30 дней → проверка пропускается

5. Сохранение результатов
   - Создание InventoryTask (статус: SUCCESS или HISTORICAL_INCONSISTENCY)
   - Создание PageCounter (только если валидация успешна)

6. Уведомление клиентов
   - WebSocket сообщение группе 'inventory_updates'

7. Синхронизация (опционально)
   - monthly_report синхронизирует счетчики при необходимости
```

### Рабочий процесс аутентификации
```
1. Пользователь посещает защищённую страницу
2. Автоматический редирект на Keycloak (если не manual=1)
3. Keycloak аутентификация → callback на /oidc/callback/
4. CustomOIDCCallbackView:
   - Проверка AllowedUser whitelist
   - Создание/обновление Django User
   - Назначение группы "Наблюдатель" новым пользователям
5. Сессия в Redis (7 дней)
6. AjaxSessionRefreshMiddleware обновляет OIDC токены для AJAX
7. Heartbeat API (/api/heartbeat/) поддерживает сессию

После logout:
- custom_logout() → /accounts/login/?manual=1
- Показ страницы выбора (Keycloak или Django логин)
```

### Cookie политика для Safari и Firefox

**Development:** Использовать `localhost` для Django и Keycloak (НЕ `127.0.0.1`).
`SESSION_COOKIE_SAMESITE = 'Lax'`, `CSRF_COOKIE_SAMESITE = 'Lax'`

**Production (USE_HTTPS=True):**
`SESSION_COOKIE_SAMESITE = 'None'`, `SESSION_COOKIE_SECURE = True`

### Рабочий процесс ежемесячной отчетности
```
1. Администратор импортирует Excel → строки MonthlyReport (скрытые по умолчанию)
2. Синхронизация → обновление счетчиков end_* из InventoryTask
3. Расчет метрик: K1 (доступность), K2 (SLA)
4. Проверка → Публикация (can_manage_month_visibility)
5. Экспорт в Excel / GLPI

Real-time совместное редактирование:
- WebSocket: /ws/monthly-report/<year>/<month>/
- Optimistic locking при конфликтах
- Флаги manual_edit для каждого поля
- Кнопка "Вернуть на автоопрос" (can_reset_auto_polling)
```

### Рабочий процесс GLPI интеграции
```
1. check_all_devices_in_glpi - ежедневно в 02:00
   - Проверяет каждое устройство в GLPI по серийному номеру
   - Результаты в GLPISync
2. cross_check_glpi_task - ежедневно в 05:00
   - Находит устройства offline/без опроса в GLPI
   - Результаты в GLPICrossCheck
3. export_monthly_report_to_glpi - по запросу
   - Экспорт данных ежемесячного отчета в GLPI
```

### Рабочий процесс Okdesk интеграции
```
1. sync_okdesk_issues - каждые 4 часа (быстрая) + 03:00 (полная)
   - Синхронизирует заявки из Okdesk API
   - Привязка к серийным номерам устройств
2. Пользователи могут:
   - Просматривать заявки устройства в модальном окне (OkdeskIssuesModal.vue)
   - Создавать новые заявки через API
   - Хранить персональные Okdesk токены (зашифрованные)
```

---

## Celery Beat расписание

| Задача | Расписание | Очередь |
|--------|-----------|---------|
| `cleanup_queue_if_needed` | XX:55 (каждый час) | daemon |
| `inventory_daemon_task` | XX:00 (каждый час) | daemon |
| `cleanup_old_inventory_data` | 03:00 ежедневно | low_priority |
| `auto_link_devices_task` | 04:00 ежедневно | low_priority |
| `check_all_devices_in_glpi` | 02:00 ежедневно | high_priority |
| `cross_check_glpi_task` | 05:00 ежедневно | low_priority |
| `sync_okdesk_issues` | */4:30 (каждые 4ч) | low_priority |
| `sync_okdesk_issues` (full) | 03:00 ежедневно | low_priority |

---

## Рабочие процессы разработки

### Добавление новой функции
```bash
1. Создание/изменение модели в <app>/models.py
2. Генерация миграции: python manage.py makemigrations
3. Применение миграции: python manage.py migrate
4. Добавление представления в <app>/views/ (или views.py)
5. Для Vue-страницы: создать компонент в frontend/src/components/<app>/
6. Регистрация URL в <app>/urls.py
7. Написание тестов
```

### Добавление Vue-компонента
```bash
1. Создать .vue файл в frontend/src/components/<app>/
2. Если нужен composable — frontend/src/composables/
3. Django шаблон: {% load vite_tags %} → {% vite_asset 'frontend/src/main.js' %}
4. Для Chart.js: обязательно Chart.register(...) нужных компонентов
5. Canvas в DOM до renderChart() — вызывать ПОСЛЕ loading.value = false + await nextTick()
```

### Запуск тестов
```bash
python manage.py test                          # Все тесты
python manage.py test inventory                # Конкретное приложение
python manage.py test --keepdb                 # Сохранение БД между запусками
python manage.py test --verbosity=2            # Подробный вывод
```

### Нагрузочное тестирование (Locust)
```bash
cd tests/locust
python setup_test_users.py                     # Создание тестовых пользователей
locust                                          # Запуск (конфиг в locust.conf)
```

---

## Общие команды

### Разработка
```bash
# Веб-сервер (WSGI - простой, без WebSockets)
python manage.py runserver 0.0.0.0:8000

# ASGI сервер (WebSockets включены)
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application

# Фронтенд dev-сервер (HMR)
cd frontend && npm run dev

# Celery worker (отдельный терминал)
celery -A printer_inventory worker --loglevel=info

# Celery beat планировщик (отдельный терминал)
celery -A printer_inventory beat --loglevel=info

# Production workers
./start_workers.sh  # Запускает 3 worker + beat
```

### База данных
```bash
python manage.py makemigrations        # Создание миграций
python manage.py migrate               # Применение миграций
python manage.py createsuperuser       # Создание администратора
python manage.py dbshell               # Консоль БД
python manage.py shell                 # Консоль Django
```

### Утилиты
```bash
# Отладка
python manage.py toggle_debug --on/--off/--status

# Данные
python manage.py cleanup_old_tasks              # Очистка старых задач
python manage.py import_flask_db path/to/db     # Импорт из Flask
python manage.py import_printers_xlsx file.xlsx # Импорт принтеров из Excel

# Доступ
python manage.py manage_whitelist --add/--list  # Белый список
python manage.py bootstrap_roles                # Создание групп прав
python manage.py setup_keycloak_groups          # Настройка Keycloak групп

# Интеграции
python manage.py sync_glpi                      # Синхронизация с GLPI
python manage.py check_glpi                     # Проверка устройств в GLPI
python manage.py import_okdesk_issues           # Импорт заявок Okdesk
python manage.py enrich_okdesk_serials          # Привязка заявок к серийникам

# Контракты
python manage.py contracts_import_xlsx file.xlsx  # Импорт контрактов
python manage.py import_cartridges_xlsx file.xlsx # Импорт картриджей
python manage.py link_devices_by_serial           # Связь устройств по серийнику
python manage.py sync_printer_models              # Синхронизация моделей принтеров

# Отчеты
python manage.py recompute_month                 # Пересчёт месяца
python manage.py sync_inventory_debug            # Отладка синхронизации

# Мониторинг
python manage.py celery_monitor                  # Мониторинг Celery
python manage.py test_errors --test-all          # Тест страниц ошибок

# Production
python manage.py collectstatic --noinput         # Сбор статики
```

---

## URL паттерны

### Основные маршруты
- `/` - Главная (перенаправляет на inventory)
- `/admin/` - Админка Django
- `/accounts/login/` - Страница входа (login_choice)
- `/accounts/logout/` - Выход (custom_logout → login с manual=1)
- `/accounts/django-login/` - Django логин
- `/accounts/access-denied/` - Keycloak access denied
- `/oidc/callback/` - OIDC callback (CustomOIDCCallbackView)
- `/oidc/authenticate/` - Начало OIDC аутентификации
- `/api/heartbeat/` - Session keepalive
- `/api/reauth-complete/` - Завершение реавторизации
- `/permissions/` - Обзор прав пользователя
- `/api/theme/` - GET/POST тема пользователя
- `/api/okdesk-token/` - GET/POST токен Okdesk

### Inventory `/inventory/`
- `/` - Список принтеров (Vue)
- `/add/` - Добавить принтер (Vue форма)
- `/<pk>/edit-form/` - Редактировать принтер (Vue форма)
- `/<pk>/edit/` - API обработка формы (POST)
- `/<pk>/delete/` - Удалить принтер
- `/<pk>/history/` - История опросов
- `/<pk>/change-history/` - История изменений принтера
- `/<pk>/run/` - Запуск опроса
- `/run_all/` - Массовый опрос
- `/<pk>/web-parser/` - Настройка веб-парсинга (Vue)
- `/export/` - Экспорт в Excel
- `/export-amb/` - Экспорт АМБ (Vue)
- `/api/printers/` - JSON список принтеров
- `/api/printer/<pk>/` - JSON детали принтера
- `/api/probe-serial/` - Проверка серийного номера
- `/api/models-by-manufacturer/` - Модели по производителю
- `/api/all-printer-models/` - Все модели
- `/api/system-status/` - Статус системы
- `/api/status-statistics/` - Статистика статусов
- `/api/web-parser/*` - API веб-парсинга (rules, test-xpath, fetch-page, proxy-page, templates)

### Contracts `/contracts/`
- `/` - Список устройств (Vue)
- `/old/` - Старый HTML список
- `/new/` - Создание устройства
- `/<pk>/edit/` - Редактирование
- `/api/devices/` - API списка для Vue
- `/api/filters/` - Фильтры для Vue
- `/api/<pk>/update/` - Обновление через API
- `/api/<pk>/delete/` - Удаление через API
- `/api/<pk>/history/` - История изменений
- `/export/` - Экспорт в Excel
- `/<pk>/email/` - Генерация email

### Monthly Report `/monthly-report/`
- `/` - Список месяцев
- `/<YYYY-MM>/` - Детали месяца
- `/upload/` - Загрузка Excel
- `/history/<pk>/` - История изменений записи
- `/month-changes/<year>/<month>/` - Изменения за месяц
- `/api/months/` - JSON список месяцев
- `/api/month/<year>/<month>/` - JSON детали месяца
- `/api/update-counters/<pk>/` - Обновление счетчиков
- `/api/sync/<year>/<month>/` - Синхронизация из inventory
- `/api/month-users-stats/<year>/<month>/` - Статистика по пользователям
- `/api/month-diff/<year>/<month>/` - Diff между месяцами
- `/api/month-changes/<year>/<month>/` - Список изменений
- `/api/device-report/<year>/<month>/<serial>/` - Отчет по устройству
- `/api/glpi-export/start/` - Запуск экспорта в GLPI
- `/api/glpi-export/status/<task_id>/` - Статус экспорта
- `/<year>/<month>/export-excel/` - Экспорт месяца в Excel
- + toggle-month-published, toggle-auto-sync, reset-manual-flag, delete-month и др.

### Integrations `/integrations/`
- `/glpi/check-device/<device_id>/` - Проверка устройства в GLPI
- `/glpi/check-multiple/` - Массовая проверка GLPI
- `/glpi/sync-status/<device_id>/` - Статус синхронизации GLPI
- `/glpi/conflicts/` - Конфликты GLPI (несколько совпадений)
- `/glpi/not-found/` - Устройства не найденные в GLPI
- `/okdesk/issues/<device_id>/` - Заявки Okdesk для устройства
- `/okdesk/create-issue/` - Создание заявки Okdesk

### Dashboard `/dashboard/`
- `/` - Главная страница дашборда (Vue)
- `/api/printer-status/` - Статусы принтеров
- `/api/poll-stats/` - Статистика опросов
- `/api/low-consumables/` - Низкий уровень расходников
- `/api/problem-printers/` - Проблемные принтеры
- `/api/print-trend/` - Тренды печати
- `/api/org-summary/` - Сводка по организациям
- `/api/recent-activity/` - Последняя активность
- `/api/organizations/` - Список организаций
- `/api/org-devices/` - Устройства организации
- `/api/org-devices/export/` - Экспорт устройств организации
- `/api/glpi-cross-check/` - Кросс-проверка GLPI
- `/api/glpi-cross-check/refresh/` - Обновить кросс-проверку
- `/api/print-trend/export/` - Экспорт трендов
- `/api/poll-stats/export/` - Экспорт статистики опросов

### Отладочные маршруты (только DEBUG=True)
- `/debug/errors/` - Меню тестирования ошибок (400, 403, 404, 405, 500, CSRF)

---

## Фронтенд — Vue-компоненты

### Inventory
- `PrinterListPage.vue` - Главная страница со списком принтеров
- `PrinterTable.vue` - Таблица принтеров
- `PrinterFilters.vue` - Фильтры
- `PrinterModal.vue` - Модальное окно деталей
- `PrinterForm.vue` - Форма создания/редактирования
- `ColumnSelector.vue` - Выбор видимых колонок
- `DeleteConfirmModal.vue` - Подтверждение удаления
- `WebParserPage.vue` - Настройка веб-парсинга
- `AmbExportPage.vue` - Экспорт АМБ
- `HistoryChart.vue` - График истории опросов

### Contracts
- `ContractDeviceListPage.vue` - Список устройств по контрактам
- `ContractDeviceTable.vue` - Таблица устройств
- `ContractDeviceFilters.vue` - Фильтры
- `ContractDeviceModal.vue` - Модальное окно
- `ColumnFilter.vue` - Фильтр колонок
- `OkdeskIssuesModal.vue` - Заявки Okdesk для устройства

### Monthly Report
- `MonthListPage.vue` - Список месяцев
- `MonthDetailPage.vue` - Детали месяца
- `MonthReportTable.vue` - Таблица отчета (фиксированная шапка)
- `CounterCell.vue` - Ячейка счетчика
- `UploadExcelPage.vue` - Загрузка Excel
- `ChangeHistoryPage.vue` - История изменений
- `MonthChangesPage.vue` - Изменения за месяц
- `DeviceInfoModal.vue` - Информация об устройстве

### Dashboard
- `DashboardPage.vue` - Главная страница дашборда
- `DashboardFilters.vue` - Фильтры (организация, период)
- Виджеты (`dashboard/widgets/`):
  - `PrinterStatusCards.vue` - Карточки статусов
  - `PollStatsChart.vue` - График статистики опросов
  - `PrintVolumeTrendChart.vue` - Тренд объемов печати
  - `LowConsumablesTable.vue` - Низкие расходники
  - `ProblemPrintersTable.vue` - Проблемные принтеры
  - `OrgSummaryTable.vue` - Сводка по организациям
  - `OrgDetailModal.vue` - Детали организации
  - `RecentActivityTable.vue` - Последняя активность
  - `GLPICrossCheckWidget.vue` - Кросс-проверка GLPI

### Common
- `Pagination.vue` - Пагинация
- `ToastContainer.vue` - Toast уведомления
- `FixedScrollbar.vue` - Фиксированный скроллбар
- `SearchableSelect.vue` - Поиск в выпадающем списке
- `MultiSelect.vue` - Мультиселект
- `OkdeskTokenModal.vue` - Управление токеном Okdesk
- `ChangeHistoryModal.vue` - Модальное окно истории

### Composables
- `useUrlFilters.js` - Фильтры через URL параметры
- `useWebSocket.js` - WebSocket соединение
- `useToast.js` - Toast уведомления
- `useColumnVisibility.js` - Видимость колонок
- `useColumnResize.js` - Изменение размера колонок
- `useScrollProgress.js` - Прогресс скролла
- `useFloatingScrollbar.js` - Плавающий скроллбар
- `useWidgetLoader.js` - Ленивая загрузка виджетов дашборда
- `usePrinters.js` - Работа с принтерами
- `useCrossFiltering.js` - Кросс-фильтрация

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
GLPI_USER=          # Пользователь для sudo (Linux/Mac)
GLPI_USE_SUDO=False # Использовать sudo для запуска
HTTP_CHECK=True     # Включить веб-парсинг
POLL_INTERVAL_MINUTES=60
```

### Защита от аномальных счетчиков (Kyocera bug)
```bash
ANOMALY_CHECK_TIME_WINDOW_HOURS=24  # Окно строгой проверки (часы)
ANOMALY_JUMP_THRESHOLD=5000         # Порог аномального скачка (страниц)
ANOMALY_SKIP_CHECK_DAYS=30          # Пропуск проверки если давно не опрашивался (дни)
```

### Опциональные
```bash
REDIS_PASSWORD=<если-установлен>
REDIS_DB=0         # Base DB (0=cache, 1=sessions, 2=inventory, 3=celery)
LOG_LEVEL=INFO
```

---

## Ключевые соглашения и лучшие практики

### Стиль кода
- **Python:** PEP 8, 4 пробела, максимум 120 символов
- **Vue:** Composition API, `<script setup>` предпочтительно
- **Импорты:** stdlib → сторонние → Django → локальные
- **Форматирование:** black + flake8

### Соглашения Django
- `select_related()` / `prefetch_related()` для N+1
- Методы `__str__()` на всех моделях
- `verbose_name` / `verbose_name_plural` в Meta
- Функциональные представления для API, CBV для CRUD

### Логирование
```python
import logging
logger = logging.getLogger(__name__)
```

### Задачи Celery
```python
@shared_task(bind=True, max_retries=3, queue="high_priority")
def my_task(self, arg):
    try:
        pass
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

### WebSocket сообщения
```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()
async_to_sync(channel_layer.group_send)(
    "inventory_updates",
    {"type": "inventory_update", "printer_id": printer.id}
)
```

---

## Отладка и устранение неполадок

### Логи
```bash
tail -f logs/django.log          # Общие ошибки
tail -f logs/errors.log          # Production
tail -f logs/celery.log          # Задачи Celery
tail -f logs/keycloak_auth.log   # Аутентификация
```

### Распространенные проблемы

**WebSockets не работают:** Запустить Daphne (не runserver), проверить Redis, путь `/ws/inventory/`

**Celery задачи не выполняются:** Проверить worker, logs/celery.log, Redis

**OIDC ошибка:** Keycloak запущен?, OIDC_CLIENT_ID/SECRET?, logs/keycloak_auth.log

**Опрос не работает:** GLPI_PATH?, доступность IP?, firewall?

**Vue компоненты не обновляются:** `cd frontend && npm run dev` (HMR), проверить `{% vite_asset %}`

**Chart.js не рендерится:** `Chart.register(...)` вызван?, canvas в DOM до renderChart()?

---

## Контрольный список развертывания

### Перед развертыванием
- [ ] `python manage.py test`
- [ ] `python manage.py makemigrations --check`
- [ ] `python manage.py migrate --plan`
- [ ] `cd frontend && npm run build`
- [ ] `python manage.py collectstatic`
- [ ] DEBUG=False, надежный SECRET_KEY
- [ ] ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS настроены

### Сервисы
- [ ] Daphne: `python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application`
- [ ] Celery workers: `./start_workers.sh`
- [ ] Celery beat (для Beat расписания)
- [ ] PostgreSQL + Redis запущены
- [ ] Keycloak realm настроен
- [ ] `python manage.py bootstrap_roles`

---

## Git рабочий процесс

### Стратегия веток
- **main** - Готовый к production код

### Сообщения коммитов
```
Добавлена поддержка веб-парсинга для принтеров HP
Fix: Устранена проблема таймаута опроса
Refactor: Извлечена логика SNMP в слой сервисов
```

---

## Дополнительные ресурсы

### Документация
- Django: https://docs.djangoproject.com/
- Celery: https://docs.celeryproject.org/
- Django Channels: https://channels.readthedocs.io/
- Vue 3: https://vuejs.org/
- Vite: https://vitejs.dev/
- Chart.js: https://www.chartjs.org/
- Bootstrap 5: https://getbootstrap.com/docs/5.0/

---

**Последнее обновление:** 2026-04-23
**Статус:** Активная разработка
