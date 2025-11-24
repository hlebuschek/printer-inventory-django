# Printer Inventory Django - Комплексный обзор кодовой базы

## Назначение проекта
Это веб-приложение на основе Django для управления и опроса сетевых принтеров (изначально мигрировано с Flask). Оно предоставляет CRUD-операции для принтеров, опрос инвентаря через SNMP и HTTP, многопоточный массовый опрос, обновления пользовательского интерфейса в реальном времени через WebSockets и возможности импорта устаревших данных.

**Ключевые возможности:**
- Управление инвентарём сетевых принтеров
- Опрос на основе SNMP и инвентаризация устройств через GLPI Agent
- HTTP веб-парсинг для страниц состояния принтера
- Обновления в реальном времени через WebSocket (Django Channels)
- Функциональность экспорта в Excel
- Ежемесячная отчётность с отслеживанием счётчиков
- Аутентификация Keycloak/OIDC с контролем доступа по белому списку
- Управление контрактами (отслеживание устройств по организациям)
- Асинхронная обработка задач (Celery + Redis)

---

## Структура каталогов

```
printer-inventory-django/
├── printer_inventory/          # Настройки и конфигурация проекта Django
│   ├── settings.py             # Основные настройки Django (23KB)
│   ├── urls.py                 # Корневая маршрутизация URL
│   ├── asgi.py                 # Конфигурация ASGI (WebSockets)
│   ├── wsgi.py                 # Конфигурация WSGI
│   ├── celery.py               # Конфигурация приложения Celery
│   ├── auth_backends.py        # Аутентификация Keycloak/OIDC (13KB)
│   ├── auth_views.py           # Представления входа/выхода
│   ├── middleware.py           # Безопасность и пользовательское промежуточное ПО
│   ├── errors.py               # Обработчики ошибок (400, 403, 404, 500)
│   └── debug_views.py          # Тестирование ошибок в режиме отладки
│
├── inventory/                  # Основное приложение управления инвентарём
│   ├── models.py               # 377 строк - Printer, InventoryTask, PageCounter
│   ├── views/                  # Модулизированные представления (94 строки)
│   │   ├── __init__.py         # Экспортирует все функции представлений
│   │   ├── printer_views.py    # CRUD-операции (21KB)
│   │   ├── api_views.py        # Конечные точки REST API (17KB)
│   │   ├── export_views.py     # Экспорт Excel/AMB (14KB)
│   │   ├── web_parser_views.py # Пользовательский интерфейс веб-парсинга (23KB)
│   │   └── report_views.py     # Представления отчётов
│   ├── services.py             # 611 строк - Основная логика опроса
│   ├── tasks.py                # Задачи Celery для асинхронного опроса
│   ├── web_parser.py           # Движок веб-парсинга XPath/Regex
│   ├── utils.py                # Утилиты GLPI, SNMP, проверки
│   ├── consumers.py            # WebSocket-потребитель (Channels)
│   ├── routing.py              # Маршрутизация WebSocket
│   ├── forms.py                # Формы Django
│   ├── admin.py                # Настройка админ-панели Django
│   ├── urls.py                 # Шаблоны URL приложения
│   ├── management/commands/    # 8+ команд управления
│   │   ├── import_flask_db.py
│   │   ├── import_inventory_xml.py
│   │   ├── cleanup_old_tasks.py
│   │   ├── toggle_debug.py
│   │   └── ... (команды миграции и диагностики)
│   ├── migrations/
│   └── templates/inventory/    # Шаблоны приложения
│
├── contracts/                  # Приложение управления контрактами/устройствами
│   ├── models.py               # 10KB - DeviceModel, Cartridge, ContractDevice
│   ├── views.py                # 33KB - CBV для контрактов
│   ├── forms.py                # 11KB - Формы контрактов
│   ├── admin.py                # 23KB - Настройка админ-панели
│   ├── utils.py                # Утилиты связывания Excel
│   ├── management/commands/    # 3 команды управления
│   │   ├── contracts_import_xlsx.py
│   │   ├── import_cartridges_xlsx.py
│   │   └── link_devices_by_serial.py
│   ├── templatetags/           # Пользовательские фильтры шаблонов
│   └── templates/contracts/
│
├── access/                     # Контроль доступа и аутентификация
│   ├── models.py               # Модель AllowedUser (белый список)
│   ├── views.py                # Отказ в доступе Keycloak, проверки ролей
│   ├── middleware.py           # Промежуточное ПО контроля доступа к приложению
│   ├── admin.py                # Администрирование белого списка пользователей
│   ├── management/commands/    # 4 команды настройки
│   │   ├── setup_keycloak_groups.py
│   │   ├── setup_roles.py
│   │   ├── bootstrap_roles.py
│   │   └── manage_whitelist.py
│   └── templates/access/       # Страницы отказа в доступе
│
├── monthly_report/             # Модуль ежемесячной отчётности
│   ├── models.py               # 311 строк - MonthlyReport, модели синхронизации
│   ├── models_modelspec.py     # Спецификации моделей устройств
│   ├── views.py                # 49KB - CRUD отчётов и отчётность
│   ├── forms.py                # 14KB - Формы отчётов
│   ├── services.py             # 8KB - Сервисы расчётов
│   ├── services_inventory.py   # 11KB - Синхронизация инвентаря
│   ├── services_inventory_sync.py  # 16KB - Расширенная логика синхронизации
│   ├── integrations/           # Адаптеры интеграции
│   │   ├── inventory_adapter.py
│   │   ├── inventory_hooks.py
│   │   └── inventory_batch.py
│   ├── services/               # Сервисные модули
│   │   ├── audit_service.py
│   │   └── excel_export.py
│   ├── specs.py                # Спецификации моделей устройств
│   ├── signals.py              # Сигналы Django
│   ├── admin.py                # 7KB - Администрирование отчётов
│   ├── management/commands/    # 4 команды синхронизации
│   │   ├── sync_inventory_debug.py
│   │   ├── init_monthly_report_roles.py
│   │   └── check_user_permissions.py
│   └── templates/monthly_report/
│
├── templates/                  # Глобальные шаблоны
│   ├── base.html               # Основной макет с Alpine.js
│   ├── error.html              # Шаблон страницы ошибки
│   ├── registration/           # Шаблоны входа/аутентификации
│   │   ├── login_choice.html
│   │   ├── django_login.html
│   │   └── keycloak_access_denied.html
│   ├── 400.html, 403.html, 404.html, 405.html, 500.html  # Страницы ошибок
│   ├── debug/                  # Страницы тестирования ошибок отладки
│   └── partials/               # Многократно используемые компоненты шаблонов
│       ├── pagination.html
│       └── column_filter.html
│
├── static/                     # Фронтенд-ресурсы
│   ├── css/vendor/
│   │   ├── bootstrap.min.css
│   │   └── bootstrap-icons.css
│   ├── js/vendor/
│   │   ├── alpine.min.js       # Легковесный реактивный UI-фреймворк
│   │   ├── alpine-*.min.js     # Расширения Alpine
│   │   ├── bootstrap.bundle.min.js
│   │   └── chart.min.js        # Библиотека графиков
│   └── fonts/bootstrap-icons/
│
├── docs/
│   └── ERROR_HANDLING.md       # Документация обработки ошибок
│
├── manage.py                   # Скрипт управления Django
├── requirements.txt            # Зависимости Python (23 пакета)
├── daphne-requirements.txt    # Требования ASGI-сервера
├── docker-compose.yml         # Keycloak для разработки
├── start_workers.sh           # Скрипт запуска воркеров Celery
├── update_static_deps.sh      # Обновление зависимостей фронтенда
├── README.md                  # Документация проекта
└── .gitignore                # Шаблоны игнорирования Git
```

---

## Архитектура приложений Django

### 1. **inventory** - Основное управление принтерами
- **Назначение:** Управление активами принтеров, опрос инвентаря, отслеживание счётчиков страниц
- **Ключевые модели:**
  - `Organization`: Группы принтеров по организациям
  - `Printer`: Отдельные устройства принтеров с IP, сообществом SNMP, методом опроса
  - `InventoryTask`: Исторические записи опроса со статусом
  - `PageCounter`: Количество страниц и уровни расходных материалов на задачу
  - `WebParsingRule`: Правила XPath/Regex для опроса на основе веб
  - `WebParsingTemplate`: Многократно используемые шаблоны для конфигураций веб-парсинга
  - `MatchRule`: Перечисление для правил сопоставления (SN_MAC, MAC_ONLY, SN_ONLY)
  - `PollingMethod`: Перечисление (SNMP vs WEB)
  - `InventoryAccess`: Модель разрешений для контроля доступа

- **Поток данных:**
  1. Пользователь запускает ручной опрос ИЛИ планировщик запускает периодический опрос
  2. Задача Celery `run_inventory_task_priority` (высокий приоритет) или `run_inventory_task` (низкий приоритет)
  3. Сервис `run_inventory_for_printer()` выполняет SNMP (GLPI) или веб-парсинг
  4. Результаты сохраняются в `InventoryTask` + `PageCounter`
  5. Обновления WebSocket отправляются подключённым клиентам через Django Channels
  6. Приложение `monthly_report` синхронизирует данные, если настроено

### 2. **contracts** - Отслеживание контрактов устройств
- **Назначение:** Отслеживание устройств в организациях, управление совместимостью картриджей
- **Ключевые модели:**
  - `DeviceModel`: Спецификации модели (название, производитель, тип устройства)
  - `Manufacturer`: Информация OEM
  - `City`: Справочные данные о местоположении
  - `Cartridge`: Расходные материалы с артикулами
  - `DeviceModelCartridge`: M2M с флагом первичности
  - `ContractStatus`: Отслеживание статуса (цвета для значков UI)
  - `ContractDevice`: Основная запись устройства с орг., местоположением, статусом
  - Связь OneToOne с `Printer` для интеграции опроса

- **Возможности:**
  - Импорт/экспорт Excel для массовых операций
  - Связывание устройств с принтерами инвентаря
  - Отслеживание месяцев начала обслуживания
  - Отслеживание совместимости картриджей

### 3. **access** - Аутентификация и авторизация
- **Назначение:** Контроль доступа к системе
- **Ключевые модели:**
  - `AllowedUser`: Белый список Keycloak (имя пользователя, email, is_active)

- **Поток:**
  1. Keycloak OIDC возвращает утверждения пользователя
  2. `CustomOIDCAuthenticationBackend` проверяет белый список
  3. Промежуточное ПО применяет правила доступа на уровне приложения
  4. Разрешения на основе групп для отчётности, инвентаря, контрактов

### 4. **monthly_report** - Отчётность о соответствии и операциях
- **Назначение:** Отслеживание счётчиков печати, расчёт метрик SLA
- **Ключевые модели:**
  - `MonthlyReport`: Ежемесячные данные на основе строк (организация, оборудование, счётчики)
  - `MonthControl`: Настройки месяца (edit_until, is_published)
  - `BulkChangeLog`: Отслеживание изменений для массовых правок
  - `CounterChangeLog`: История отдельных изменений счётчиков
  - Автоматическая синхронизация полей из инвентаря с флагами ручного переопределения

- **Рабочий процесс:**
  1. Импорт Excel с данными оборудования (можно указать статус публикации)
  2. Синхронизация счётчиков из инвентаря (с защитой флага ручного управления)
  3. Расчёт K1 (доступность), K2 (соответствие SLA)
  4. Проверка и публикация отчета (по умолчанию скрыт для проверки)
  5. Возврат на автоопрос при необходимости (сброс флагов manual_edit_*)
  6. Экспорт отчётов для соответствия/выставления счетов

- **Кастомные права доступа (v2.1.0+):**
  - 10 кастомных прав для детального управления (см. CLAUDE.md)
  - 11 групп прав (создаются через `python manage.py init_monthly_report_roles`)
  - Управление видимостью месяцев (`can_manage_month_visibility`)
  - Возврат на автоопрос (`can_reset_auto_polling`)
  - Массовый опрос принтеров (`can_poll_all_printers`)

---

## Технологический стек

### Бэкенд
- **Django 5.2.1**: Веб-фреймворк
- **Python 3.12+**: Язык
- **PostgreSQL**: Основная база данных
- **Redis**: Кэширование, сессии, брокер Celery
- **Celery 5.3**: Очередь асинхронных задач
- **django-celery-beat 2.5**: Планировщик периодических задач
- **django-channels 4.0**: Поддержка WebSocket
- **channels-redis 4.1**: Уровень Redis для каналов
- **Daphne 4.0**: ASGI-сервер

### Аутентификация
- **mozilla-django-oidc 4.0**: OIDC-клиент
- **Keycloak 22.0**: Провайдер идентификации (предоставлен Docker Compose)

### Данные и экспорт
- **openpyxl**: Чтение/запись Excel
- **pandas**: Манипуляция данными
- **lxml 5.1**: Парсинг XML
- **psycopg[binary] 3.1**: Адаптер PostgreSQL

### Веб-скрапинг и автоматизация
- **Selenium 4.15**: Автоматизация браузера (для сложного веб-парсинга)
- **webdriver-manager 4.0**: Управление драйвером Chrome

### Фронтенд
- **Alpine.js**: Легковесный реактивный фреймворк (в base.html)
- **Bootstrap 5**: CSS-фреймворк
- **Chart.js**: Визуализация данных
- **Bootstrap Icons**: Библиотека иконок

### DevOps и утилиты
- **whitenoise 5.3**: Обслуживание статических файлов в продакшене
- **python-dotenv**: Конфигурация окружения
- **python-dateutil 2.8**: Утилиты дат
- **requests 2.28**: HTTP-клиент
- **kombu 5.3**: Передача сообщений (зависимость Celery)
- **autobahn 23.6**: Поддержка протокола WebSocket
- **pytz**: Обработка часовых поясов

---

## Структура конфигурации

### Настройки (printer_inventory/settings.py)

#### Переменные окружения
```env
# Основные
SECRET_KEY = Django секретный ключ
DEBUG = True/False
USE_HTTPS = Включить режим HTTPS

# База данных
DB_ENGINE = postgresql
DB_NAME = printer_inventory
DB_USER = postgres
DB_PASSWORD =
DB_HOST = localhost
DB_PORT = 5432

# Redis
REDIS_HOST = localhost
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_PASSWORD = (необязательно)

# Аутентификация
KEYCLOAK_SERVER_URL = http://localhost:8080
KEYCLOAK_REALM = printer-inventory
OIDC_CLIENT_ID = (из Keycloak)
OIDC_CLIENT_SECRET = (из Keycloak)
OIDC_VERIFY_SSL = True/False (для разработки)

# Сеть
ALLOWED_HOSTS = localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS = http://localhost:8000
BASE_URL = http://localhost:8000

# GLPI Agent
GLPI_PATH = /usr/bin (Linux), и т.д.
GLPI_USER = (Linux/Mac sudo)
GLPI_USE_SUDO = False/True
HTTP_CHECK = True (включить веб-парсинг)
POLL_INTERVAL_MINUTES = 60

# Часовой пояс
TIME_ZONE = Asia/Irkutsk
CELERY_TIMEZONE = Asia/Irkutsk
```

#### Установленные приложения
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'channels',
    'mozilla_django_oidc',

    'inventory',
    'contracts',
    'access',
    'monthly_report',
]
```

#### Стек промежуточного ПО
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',        # Статические файлы в продакшене
    'printer_inventory.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'mozilla_django_oidc.middleware.SessionRefresh',     # Обновление токена OIDC
    'access.middleware.AppAccessMiddleware',             # Контроль доступа на уровне приложения
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

#### Кэширование (Redis)
Три отдельные базы данных Redis для изоляции:
```python
CACHES = {
    'default': 60*15 timeout,           # DB 0 - Общий кэш
    'sessions': 60*60*24*7 timeout,     # DB 1 - Хранилище сессий
    'inventory': 60*30 timeout,         # DB 2 - Кэш инвентаря
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'
```

#### Конфигурация Celery
```python
CELERY_BROKER_URL = redis://localhost:6379/3
CELERY_RESULT_BACKEND = redis://localhost:6379/3
CELERY_TIMEZONE = 'Asia/Irkutsk'

# Очереди (на основе приоритета)
CELERY_TASK_QUEUES = (
    Queue('high_priority', routing_key='high'),  # Запросы пользователей
    Queue('low_priority', routing_key='low'),    # Периодические задачи
    Queue('daemon', routing_key='daemon'),       # Задачи демона
)

# Расписание Beat (периодические задачи)
CELERY_BEAT_SCHEDULE = {
    'inventory-daemon-every-hour': {...},           # Каждый час
    'cleanup-old-data-daily': {...},                # Ежедневно 03:00
}
```

#### Каналы (WebSockets)
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [REDIS_CHANNEL_URL]},
    }
}
# Переключается на InMemoryChannelLayer, если Redis недоступен
```

#### Логирование
Ротационные обработчики файлов для:
- `logs/django.log`: Общие логи приложения
- `logs/errors.log`: Логи уровня ошибок
- `logs/celery.log`: Логи задач Celery
- `logs/redis.log`: Предупреждения Redis
- `logs/keycloak_auth.log`: Детали аутентификации

---

## Модели и схема базы данных

### Основные связи (упрощённая ER-диаграмма)

```
Organization (1)
  ├── (1:N) Printer
  └── (1:N) ContractDevice

Printer (1)
  ├── (1:N) InventoryTask
  ├── (1:N) WebParsingRule
  ├── (1:N) PageCounter (через InventoryTask)
  ├── (0:1) ContractDevice
  └── (FK) DeviceModel (из contracts)

InventoryTask (1)
  └── (1:1) PageCounter

DeviceModel (1)
  ├── (N:M) Cartridge (через DeviceModelCartridge)
  └── (1:N) WebParsingTemplate

ContractDevice (1)
  ├── (FK) DeviceModel
  ├── (FK) ContractStatus
  ├── (FK) City
  └── (0:1) Printer (OneToOne)

MonthlyReport
  └── Синхронизирован из данных InventoryTask ежемесячно
```

### Ключевые индексы
- `Printer.ip_address` (уникальный)
- `Printer.serial_number` (db_index)
- `Printer.organization + ip_address` (составной)
- `InventoryTask.printer + status + timestamp` (составной)
- `MonthlyReport.month + serial_number + inventory_number` (составной)

---

## Маршрутизация URL и конечные точки API

### Приложение Inventory (`/printers/`)
```
GET    /printers/                          → printer_list
GET    /printers/api/printers/            → api_printers (JSON)
GET    /printers/api/printer/<id>/        → api_printer detail (JSON)
GET    /printers/<id>/run/                → запуск ручного опроса
GET    /printers/run_all/                 → опрос всех принтеров
GET    /printers/export/                  → экспорт Excel
GET    /printers/export-amb/              → экспорт отчёта AMB
POST   /printers/api/probe-serial/        → проверка серийного номера/MAC
GET    /printers/<id>/web-parser/         → UI настройки веб-парсинга
POST   /printers/api/web-parser/save-rule/ → сохранение правила парсинга
POST   /printers/api/web-parser/test-xpath/ → тест XPath
GET    /printers/api/web-parser/fetch-page/ → получение удалённой страницы
```

### Приложение Contracts (`/contracts/`)
```
GET    /contracts/                        → список контрактов
POST   /contracts/new/                    → создание контракта
GET    /contracts/<id>/edit/              → редактирование контракта
POST   /contracts/api/<id>/update/        → обновление API
POST   /contracts/api/<id>/delete/        → удаление API
GET    /contracts/export/                 → экспорт Excel
POST   /contracts/api/lookup-by-serial/   → поиск по серийному номеру
```

### Приложение Monthly Report (`/monthly-report/`)
```
GET    /monthly-report/                   → список отчётов
POST   /monthly-report/import/            → импорт Excel
GET    /monthly-report/<id>/edit/         → редактирование отчёта
POST   /monthly-report/api/sync/          → синхронизация из инвентаря
```

### Аутентификация (`/accounts/`)
```
GET    /accounts/login/                   → выбор входа (Django/Keycloak)
GET    /accounts/django-login/            → форма входа Django
GET    /accounts/logout/                  → выход
GET    /oidc/callback/                    → обратный вызов Keycloak OIDC
GET    /accounts/access-denied/           → страница отказа в доступе
```

---

## Структура представлений и шаблонов

### Организация представлений (inventory/views/)
```python
# printer_views.py (21KB)
├── printer_list(request)              # Список + фильтр
├── add_printer(request)               # Форма создания
├── edit_printer(request)              # Форма обновления
├── delete_printer(request)            # Удаление с подтверждением
├── run_inventory(request)             # Запуск одного опроса
├── run_inventory_all(request)         # Запуск всех опросов
└── history_view(request)              # Показ истории опросов

# api_views.py (17KB)
├── api_printers(request)              # JSON список
├── api_printer(request)               # JSON детали
├── api_probe_serial(request)          # Проверка серийного номера/MAC
├── api_models_by_manufacturer(request) # Данные выпадающего списка
├── api_system_status(request)         # Состояние системы
└── api_status_statistics(request)     # Статистика опросов

# export_views.py (14KB)
├── export_excel(request)              # Полный экспорт инвентаря
├── export_amb(request)                # Формат отчёта AMB
└── generate_email_from_inventory(request) # Генерация email

# web_parser_views.py (23KB)
├── web_parser_setup(request)          # UI веб-парсинга
├── save_web_parsing_rule(request)     # Сохранение правила
├── test_xpath(request)                # Тест XPath
├── fetch_page(request)                # Получение через прокси
├── execute_action(request)            # Действия перед парсингом
├── export_printer_xml(request)        # Экспорт как XML
├── get_templates(request)             # Получение шаблонов
├── save_template(request)             # Сохранение шаблона
├── apply_template(request)            # Применение шаблона к принтеру
└── delete_template(request)           # Удаление шаблона

# report_views.py
└── Представления отчётности/статистики
```

### Иерархия шаблонов
```
base.html (Основной макет с Alpine.js)
├── inventory/printer_list.html
├── inventory/printer_form.html
├── inventory/web_parser.html
├── contracts/list.html
├── monthly_report/report_list.html
├── registration/login_choice.html
└── error.html (Обработка ошибок)
```

---

## Сервисы и бизнес-логика

### inventory/services.py (611 строк)
Основная оркестрация опроса:
```python
# Опрос на основе GLPI
run_inventory_for_printer(printer_id, xml_path=None)
  → _get_glpi_paths() → Запуск glpi-netinventory/glpi-netdiscovery
  → Парсинг вывода XML → Извлечение информации об устройстве, счётчиков страниц, MAC
  → Проверка по истории → Сохранение в InventoryTask/PageCounter
  → Отправка обновления WebSocket → Возврат успеха/ошибки

# Опрос на основе веб (резервный)
execute_web_parsing(printer) → [через web_parser.py]
  → Получение страницы (с Selenium при необходимости)
  → Применение правил XPath
  → Извлечение значений
  → Применение преобразований regex
  → Возврат структурированных данных
```

### inventory/tasks.py (задачи Celery)
```python
@shared_task
run_inventory_task_priority(printer_id, user_id, xml_path)
  → Опросы пользователей с высоким приоритетом
  → Макс. повторов: 2, ограничение скорости: 30/мин
  → Ограничение времени: 5 минут

@shared_task
run_inventory_task(printer_id)
  → Периодические опросы с низким приоритетом
  → Ограничение скорости: 100/мин
  → Ограничение времени: 10 минут

@shared_task
inventory_daemon_task()
  → Запускается каждый час (расписание Beat)
  → Проверки состояния, очистка

@shared_task
cleanup_old_inventory_data()
  → Запускается ежедневно в 03:00
  → Удаление устаревших записей
```

### monthly_report/services.py и services_inventory_sync.py
```python
# Синхронизация счётчиков из инвентаря
sync_from_inventory(month, organization)
  → Запрос последней InventoryTask для каждого устройства
  → Обновление счётчиков MonthlyReport (с учётом ручных флагов)
  → Пересчёт итогов

# Расчёт метрик
calculate_k1(normative, actual_downtime)
  → K1 = ((A - D) / A) * 100%

calculate_k2(non_overdue, total)
  → K2 = (L / W) * 100%
```

### inventory/web_parser.py (18KB)
Продвинутый веб-скрапинг:
```python
execute_web_parsing(printer, rules)
  → Открытие браузера/получение страницы (Selenium/requests)
  → Для каждого правила:
    - Извлечение через XPath
    - Применение шаблонов regex
    - Обработка вычисляемых полей (формулы)
  → Возврат словаря извлечённых данных

# Поддерживает:
- Сложные выражения XPath
- Группы захвата regex
- Действия перед парсингом (клик, ожидание, внедрение скриптов)
- Вычисляемые поля (на основе формул)
```

---

## Аутентификация и авторизация

### Поток Keycloak/OIDC
```
1. Пользователь посещает /accounts/login/
2. Выбирает "Войти через Keycloak" или "Вход Django"
3. Keycloak перенаправляет на форму входа
4. После входа обратный вызов к /oidc/callback/
5. CustomOIDCAuthenticationBackend.verify_claims():
   - Проверка белого списка (таблица AllowedUser)
   - Проверка флага is_active
   - Создание пользователя Django при необходимости
6. Пользователь вошёл, сессия хранится в Redis
7. Промежуточное ПО SessionRefresh обновляет токен при истечении
```

### Модель разрешений
```
# Таблица: access.AllowedUser (Белый список)
- username (уникальный, из Keycloak)
- email
- is_active (мягкое отключение)
- added_at, added_by

# Группы Django (созданы через команды управления)
- Inventory Admins (запуск опросов, экспорт)
- Contracts Managers (редактирование устройств, контрактов)
- Report Viewers (просмотр ежемесячных отчётов)

# Разрешения на уровне объектов
APP_ACCESS_RULES = {
    'inventory': 'inventory.access_inventory_app',
    'contracts': 'contracts.access_contracts_app',
}

# Разрешения функций (через пользовательские разрешения)
- access_inventory_app
- run_inventory
- export_printers
- edit_counters_start / edit_counters_end
- sync_from_inventory
```

---

## WebSockets и функции реального времени

### Настройка (Django Channels)
```python
# ASGI (printer_inventory/asgi.py)
application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(inventory.routing.websocket_urlpatterns)
    )
})

# Потребитель (inventory/consumers.py)
class InventoryConsumer(AsyncJsonWebsocketConsumer):
    async def connect():
        → Добавление в группу 'inventory_updates'
        → Принятие соединения

    async def disconnect():
        → Удаление из группы

    async def inventory_start(event):
        → Отправка клиенту: опрос начат

    async def inventory_update(event):
        → Отправка клиенту: результат опроса
```

### Подключение клиента
```javascript
// В шаблоне (Alpine.js)
const ws = new WebSocket('ws://localhost:5000/ws/inventory/');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Обновление UI с data.message, data.status
};
```

### Рассылка обновлений
```python
# Из services.py после опроса
channel_layer = get_channel_layer()

async_to_sync(channel_layer.group_send)('inventory_updates', {
    'type': 'inventory_update',
    'printer_id': printer.id,
    'status': 'SUCCESS',
    'message': 'Poll completed',
    'timestamp': now.isoformat(),
})
```

---

## Настройка тестирования

### Файлы тестов
- `inventory/tests.py`: Тесты приложения инвентаря
- `contracts/tests.py`: Тесты моделей контрактов
- `access/tests.py`: Тесты контроля доступа
- `monthly_report/tests.py`: Тесты расчётов отчётов

### Шаблоны тестов
- Модульные тесты для моделей и сервисов
- Тесты представлений с аутентифицированными запросами
- Тесты задач Celery (имитация Redis)
- Тесты валидации форм

### Запуск тестов
```bash
python manage.py test                        # Все тесты
python manage.py test inventory              # Для конкретного приложения
python manage.py test --verbosity=2          # Подробный вывод
python manage.py test --keepdb               # Быстрее (пропуск миграций)
```

---

## Команды управления

### База данных и настройка
```bash
# Первоначальная настройка
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput

# Роли и доступ
python manage.py bootstrap_roles              # Создание начальных ролей
python manage.py setup_roles                  # Настройка в Keycloak
python manage.py manage_whitelist --add <username> --email <email>

# Начальные данные
python manage.py import_flask_db              # Импорт устаревшего Flask SQLite
python manage.py contracts_import_xlsx <file.xlsx>
python manage.py import_cartridges_xlsx <file.xlsx>
```

### Отладка и обслуживание
```bash
python manage.py toggle_debug --status        # Проверка режима DEBUG
python manage.py toggle_debug --on
python manage.py toggle_debug --off
python manage.py test_errors --test-all       # Тест обработчиков ошибок

python manage.py cleanup_old_tasks            # Удаление старых записей опросов
python manage.py check_inventory_tasks        # Аудит статуса задач
python manage.py sync_printer_models          # Синхронизация моделей устройств
python manage.py redis_management --list      # Статистика Redis

python manage.py celery_monitor               # Мониторинг задач Celery
python manage.py diagnose_daemon              # Диагностика демона
```

---

## Рабочий процесс разработки

### Локальная настройка
```bash
# 1. Виртуальная среда
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# 2. Установка зависимостей
pip install -r requirements.txt

# 3. Создание .env
cp .env.example .env
# Редактирование с локальными настройками

# 4. База данных
python manage.py migrate
python manage.py createsuperuser

# 5. Keycloak (Docker Compose)
docker-compose up -d
# Посещение http://localhost:8080/admin
# Создание области, клиента, настройка групп

# 6. Запуск сервера разработки
python manage.py runserver 0.0.0.0:8000

# 7. Воркер Celery (отдельный терминал)
celery -A printer_inventory worker --loglevel=INFO

# 8. Celery Beat (отдельный терминал)
celery -A printer_inventory beat --loglevel=INFO
```

### Развёртывание в продакшене
```bash
# Сборка
python manage.py collectstatic --noinput
python manage.py migrate

# Запуск с Daphne (ASGI)
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application

# Воркеры Celery (использовать start_workers.sh)
./start_workers.sh

# Обратный прокси (nginx)
upstream asgi {
    server 127.0.0.1:5000;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    location / {
        proxy_pass http://asgi;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://asgi;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Ключевые конфигурационные файлы
- `.env`: Переменные окружения (секреты, хосты, учётные данные)
- `requirements.txt`: Версии пакетов Python
- `start_workers.sh`: Запуск воркеров Celery
- `docker-compose.yml`: Keycloak для разработки
- `settings.py`: Вся конфигурация Django

---

## Сводка конечных точек API

### Основные REST API
| Метод | Конечная точка | Назначение | Ответ |
|--------|----------|---------|----------|
| GET | `/printers/api/printers/` | Список всех принтеров | `{"printers": [...], "total": N}` |
| GET | `/printers/api/printer/1/` | Получить детали принтера | `{...данные принтера...}` |
| POST | `/printers/api/probe-serial/` | Проверить серийный номер/MAC | `{"is_valid": bool, "error": str}` |
| GET | `/printers/api/system-status/` | Состояние системы | `{"redis": ok, "db": ok}` |
| POST | `/printers/api/web-parser/save-rule/` | Сохранить правило парсинга | `{"id": N, "success": bool}` |
| POST | `/contracts/api/<id>/update/` | Обновить контракт | `{...обновлённые данные...}` |
| GET | `/monthly-report/api/sync/` | Синхронизировать из инвентаря | `{"synced": N, "errors": [...]}` |

### Конечные точки не-REST (на основе форм)
- GET `/printers/` - HTML-список с фильтрами
- POST `/printers/add/` - Создание нового принтера
- POST `/printers/<id>/edit/` - Обновление принтера
- POST `/printers/<id>/delete/` - Удаление принтера
- GET `/printers/export/` - Скачивание файла Excel
- GET `/printers/<id>/run/` - Запуск опроса (перенаправление)

---

## Обработка ошибок

### Пользовательские страницы ошибок
- `400.html`: Неверный запрос
- `403.html`: Запрещено / Ошибки CSRF (`403_csrf.html`)
- `404.html`: Не найдено
- `405.html`: Метод не разрешён
- `500.html`: Ошибка сервера
- `error.html`: Общий шаблон ошибки

### Логирование ошибок
- Режим отладки: Красивые HTML-страницы ошибок
- Продакшен: Пользовательские шаблоны ошибок + логирование в `logs/errors.log`
- Ошибки CSRF: `logs/django.log`
- Ошибки аутентификации: `logs/keycloak_auth.log`

### Тестирование ошибок (режим отладки)
```
GET /debug/errors/          → Меню тестирования ошибок
GET /debug/errors/400/      → Тест обработчика 400
GET /debug/errors/403/      → Тест обработчика 403
GET /debug/errors/404/      → Тест обработчика 404
GET /debug/errors/500/      → Тест обработчика 500
GET /debug/errors/csrf/     → Тест формы CSRF
POST /debug/errors/csrf/submit/ → Тест отправки CSRF
```

---

## Соображения производительности

### Стратегия кэширования
- **Кэш инвентаря** (DB 2): TTL 30 минут
  - Список моделей, список организаций
  - Предложения шаблонов
- **Общий кэш** (DB 0): TTL 15 минут
  - Статистика, подсчёты статусов
- **Кэш сессий** (DB 1): TTL 7 дней
  - Пользовательские сессии через Redis

### Оптимизация базы данных
- Составные индексы для частых паттернов запросов
- `select_related()` для запросов ForeignKey
- `prefetch_related()` для обратных поисков
- Пагинированные представления списков (не всё сразу)

### Оптимизация Celery
- **Очередь высокого приоритета**: 4 воркера, немедленное выполнение
- **Очередь низкого приоритета**: 2 воркера, может быть отложено
- **Очередь демона**: 1 воркер, минимальная параллельность
- **Макс. задач на потомка**: 50-200 (предотвращает утечки памяти)
- **Множитель предварительной загрузки**: 1 (без предварительной загрузки, немедленное подтверждение)
- **Задачи подтверждаются с опозданием**: Повтор при сбое воркера

### Оптимизация WebSocket
- Уровень канала Redis (против в памяти)
- Групповая рассылка (не индивидуальные каналы)
- Сериализация JSON (компактная)
- Автоматический переход на в памяти, если Redis недоступен

---

## Сводка размеров файлов
- `printer_inventory/settings.py`: 23KB
- `inventory/services.py`: 611 строк
- `inventory/views/web_parser_views.py`: 23KB
- `inventory/views/printer_views.py`: 21KB
- `monthly_report/views.py`: 49KB (самый большой)
- `contracts/views.py`: 33KB
- `contracts/admin.py`: 23KB

Всего строк Python: ~8,000 (исключая миграции, вендорные библиотеки)

---

## График ключевых зависимостей
```
Django 5.2
├── Channels 4.0 (WebSockets)
├── Celery 5.3 (Асинхронные задачи)
│   └── Redis (Брокер + Результаты)
├── OIDC (Mozilla) (Аутентификация)
│   └── Keycloak (Провайдер идентификации)
├── PostgreSQL (База данных)
├── WhiteNoise (Статические файлы)
├── django-redis (Кэш)
├── pandas (Обработка данных)
├── openpyxl (Excel)
├── Selenium (Автоматизация веб)
└── lxml (Парсинг XML)
```

---

## Функции безопасности

### Защита CSRF
- `CsrfViewMiddleware` на всех POST/PUT/DELETE
- Токен в формах, заголовках AJAX
- Пользовательское представление сбоя: `custom_csrf_failure`
- Политика cookie SameSite

### Аутентификация
- OIDC через Keycloak (не на основе пароля)
- Применение белого списка (AllowedUser)
- Промежуточное ПО обновления токена
- Таймаут сессии (7 дней)

### Авторизация
- Декораторы на уровне представлений (`@login_required`)
- Промежуточное ПО контроля доступа к приложению
- Пользовательские разрешения для функций
- Проверка ролей на основе групп

### SQL-инъекция
- ORM защищает через параметризованные запросы
- Все пользовательские данные проверены/очищены

### Предотвращение XSS
- Автоэкранирование шаблонов включено
- Заголовки CSP в SecurityHeadersMiddleware
- Alpine.js (без рендеринга пользовательского HTML)

### Конфиденциальные данные
- Без секретов в коде (использовать `.env`)
- Пароли хэшированы (по умолчанию Django)
- SSL/TLS в продакшене (USE_HTTPS=True)
- Защищённые куки в продакшене

---

## Руководство по устранению неполадок

### Распространённые проблемы

**1. Сбой подключения WebSocket**
- Проверьте, что Redis работает: `redis-cli ping`
- Проверьте, что Daphne работает на правильном порту
- Проверьте источник CSRF в настройках
- Консоль разработчика браузера для ошибок подключения

**2. Задачи опроса не выполняются**
- Проверьте воркер Celery: `celery -A printer_inventory inspect active`
- Проверьте Celery Beat: `ps aux | grep celery`
- Проверьте брокер Redis: `redis-cli keys *`
- Проверьте логи задач: `logs/celery.log`

**3. Сбой аутентификации**
- Проверьте, что Keycloak работает: `curl http://localhost:8080/`
- Проверьте client_id/secret в настройках
- Проверьте белый список: `AllowedUser.objects.all()`
- Просмотрите `logs/keycloak_auth.log` для деталей

**4. Статические файлы не загружаются**
- Запустите `python manage.py collectstatic --noinput`
- Проверьте настроенное промежуточное ПО WhiteNoise
- Проверьте STATIC_ROOT и STATIC_URL в настройках
- Проверьте разрешения на каталог `staticfiles/`

**5. Ошибка подключения к базе данных**
- Проверьте, что PostgreSQL работает: `psql -U postgres`
- Проверьте учётные данные в `.env`
- Проверьте доступность DB_HOST/PORT
- Запустите миграции: `python manage.py migrate`

---

## Контрольный список развёртывания

- [ ] Установить DEBUG=False в продакшене
- [ ] Сгенерировать сильный SECRET_KEY (>50 символов)
- [ ] Настроить ALLOWED_HOSTS
- [ ] Установить USE_HTTPS=True, SECURE_SSL_REDIRECT
- [ ] Настроить CSRF_TRUSTED_ORIGINS для домена
- [ ] Настроить область Keycloak, клиента, группы
- [ ] Настроить OIDC_RP_CLIENT_ID, OIDC_RP_CLIENT_SECRET
- [ ] Настроить PostgreSQL с сильными учётными данными
- [ ] Настроить Redis с паролем (необязательно, но рекомендуется)
- [ ] Запустить `collectstatic` для всех статических файлов
- [ ] Запустить миграции: `manage.py migrate`
- [ ] Создать суперпользователя (резервный, может не использоваться, если только OIDC)
- [ ] Настроить ASGI-сервер Daphne
- [ ] Настроить воркеры Celery (через start_workers.sh или systemd)
- [ ] Настроить Celery Beat (почасовые/ежедневные задачи)
- [ ] Настроить логирование в файлы (каталог logs/)
- [ ] Настроить обратный прокси (nginx/Apache)
- [ ] Настроить SSL-сертификаты
- [ ] Протестировать страницы ошибок в продакшене (DEBUG=False)
- [ ] Добавить начальных пользователей в белый список в таблице AllowedUser
- [ ] Запланировать регулярные резервные копии (PostgreSQL, логи)

---

## Полезные ресурсы

- Документация Django: https://docs.djangoproject.com/
- Channels: https://channels.readthedocs.io/
- Celery: https://docs.celeryproject.org/
- Keycloak: https://www.keycloak.org/documentation
- GLPI Agent: https://github.com/glpi-project/glpi-agent
- PostgreSQL: https://www.postgresql.org/docs/
- Redis: https://redis.io/documentation

---

## Следующие шаги для AI-ассистентов

1. **Обзор кода**: Начните с `inventory/services.py` - основная логика опроса
2. **Исправления ошибок**: Проверьте `logs/*.log` на наличие ошибок
3. **Функции**: Добавьте в представления в каталоге `inventory/views/`
4. **Изменения базы данных**: Создайте миграции, обновите модели
5. **Задачи Celery**: Добавьте в `inventory/tasks.py` для асинхронной работы
6. **Шаблоны**: Измените `templates/` для изменений UI
7. **Тесты**: Добавьте в файлы `*/tests.py`
8. **Развёртывание**: Следуйте контрольному списку выше

Эта кодовая база следует лучшим практикам Django с чистым разделением ответственности, комплексным логированием и архитектурой, готовой к продакшену.
