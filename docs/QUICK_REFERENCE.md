# Краткий справочник - Printer Inventory Django

## Что это за проект?
Django веб-приложение для управления сетевыми принтерами с SNMP-опросом, веб-парсингом, обновлениями в реальном времени и отчетностью.

## Ключевая статистика
- **Файлов Python**: ~8,000 строк кода (без учета миграций)
- **Django приложений**: 4 (inventory, contracts, access, monthly_report)
- **База данных**: PostgreSQL с 9 основными моделями
- **API**: 20+ REST эндпоинтов
- **WebSockets**: Обновления инвентаря в реальном времени через Django Channels
- **Фоновые задачи**: Celery с 3 очередями приоритетов
- **Аутентификация**: Keycloak/OIDC с белым списком

---

## Структура проекта с первого взгляда

| Директория | Назначение | Файлы |
|-----------|---------|-------|
| `printer_inventory/` | Конфигурация Django проекта | settings.py, urls.py, asgi.py, wsgi.py |
| `inventory/` | Управление принтерами | models (377 строк), services (611 строк), views (94 строки экспортированы) |
| `contracts/` | Отслеживание устройств | models (10KB), views (33KB), 3 команды импорта |
| `access/` | Аутентификация | Белый список Keycloak, middleware, 4 команды настройки |
| `monthly_report/` | Отчетность | models (311 строк), views (49KB), логика синхронизации |
| `templates/` | HTML UI | base.html (Alpine.js), страницы ошибок, шаблоны форм |
| `static/` | Ресурсы | Bootstrap 5, Alpine.js, Chart.js, иконки |
| `docs/` | Документация | ERROR_HANDLING.md, CODEBASE_OVERVIEW.md (этот!) |

---

## Технологический стек (кратко)

**Backend:**
- Django 5.2 + PostgreSQL + Redis
- Celery (асинхронные задачи) + Celery Beat (планировщик)
- Daphne (ASGI сервер для WebSockets)

**Аутентификация:**
- Keycloak 22.0 (OIDC провайдер)
- mozilla-django-oidc

**Frontend:**
- Alpine.js (реактивный UI без этапа сборки)
- Bootstrap 5 + Bootstrap Icons
- Chart.js (графики)

**Обработка данных:**
- GLPI Agent (SNMP опрос)
- Selenium (веб-автоматизация)
- XPath + Regex (веб-парсинг)
- openpyxl (импорт/экспорт Excel)
- pandas (манипуляция данными)

---

## Ключевые архитектурные паттерны

### 1. Django приложения (модульность)
Каждое приложение самодостаточно с моделями, представлениями, формами, шаблонами, админкой, URL.

### 2. Слой сервисов (бизнес-логика)
Тяжелая работа в `services.py` - не в представлениях. Пример: `run_inventory_for_printer()`

### 3. Очередь задач (асинхронная работа)
Длительные операции через Celery задачи (опрос, импорт, синхронизация) - поддерживает отзывчивость UI.

### 4. Кэширование (производительность)
3 базы данных Redis:
- DB 0: Общий кэш (TTL 15 мин)
- DB 1: Сессии (TTL 7 дней)
- DB 2: Инвентарь (TTL 30 мин)

### 5. WebSockets (реальное время)
Django Channels + Redis → Отправка обновлений подключенным клиентам по завершении опросов.

### 6. Обработка ошибок (готово к production)
Пользовательские страницы ошибок + логирование в файлы + заголовки безопасности.

### 7. Аутентификация (корпоративная)
OIDC через Keycloak + белый список (AllowedUser) + ролевые разрешения.

---

## Иерархия основных моделей

```
Organization
  ├── Printer (с IP, SNMP, организацией)
  │   ├── InventoryTask (история опросов)
  │   │   └── PageCounter (счетчики за опрос)
  │   └── WebParsingRule (правила извлечения)
  │       └── WebParsingTemplate (переиспользуемые конфиги)
  │
  └── ContractDevice (устройство в контрактах)
      ├── DeviceModel (спецификации)
      │   ├── Manufacturer
      │   ├── Cartridge (расходники)
      │   └── ContractStatus (статус)
      └── OneToOne → Printer (связь с инвентарем)

MonthlyReport (синхронизировано из данных InventoryTask)
```

---

## Основные рабочие процессы

### Процесс опроса
```
1. Пользователь нажимает "Run Poll" ИЛИ срабатывает планировщик
2. Celery задача: run_inventory_task_priority() [пользователь] или run_inventory_task() [периодическая]
3. Сервис: run_inventory_for_printer()
   - Вариант A: GLPI Agent → SNMP опрос → парсинг XML
   - Вариант B: Web Parser → извлечение XPath + Regex
4. Сохранение в InventoryTask + PageCounter
5. Отправка WebSocket обновления: "Poll completed"
6. Опционально: Синхронизация в счетчики monthly_report
```

### Процесс аутентификации
```
1. Пользователь заходит на /accounts/login/
2. Выбирает Keycloak или Django вход
3. Keycloak перенаправляет на форму входа
4. После аутентификации, обратный вызов на /oidc/callback/
5. Backend проверяет белый список AllowedUser
6. Создает Django User при необходимости
7. Устанавливает сессию в Redis
8. Middleware автоматически обновляет токен перед истечением
```

### Процесс месячной отчетности
```
1. Администратор импортирует Excel с данными оборудования
2. Создаются строки MonthlyReport (с начальными счетчиками)
3. Синхронизация из инвентаря: получение последней InventoryTask для каждого устройства
4. Обновление конечных счетчиков (с учетом флагов ручного редактирования)
5. Пересчет K1 (доступность) и K2 (SLA)
6. Экспорт обратно в Excel для выставления счетов/соответствия
```

---

## Типичные задачи для AI-помощников

### Добавить новую функцию
1. Создать модель в `apps/models.py`
2. Создать миграцию: `python manage.py makemigrations`
3. Добавить представление(я) в `apps/views.py` или `apps/views/`
4. Добавить шаблон в `templates/appname/`
5. Добавить URL в `apps/urls.py`
6. Зарегистрировать в Django admin (`apps/admin.py`)
7. Добавить тесты в `apps/tests.py`

### Добавить API эндпоинт
1. Создать функцию представления в `inventory/views/api_views.py`
2. Добавить декоратор @json_response (или вернуть JsonResponse)
3. Зарегистрировать URL в `inventory/urls.py`
4. Задокументировать в QUICK_REFERENCE.md

### Добавить периодическую задачу
1. Создать `@shared_task` в `apps/tasks.py`
2. Зарегистрировать в `CELERY_BEAT_SCHEDULE` (settings.py)
3. Проверить: `python manage.py celery_monitor`
4. Логи: `logs/celery.log`

### Исправить баг
1. Проверить логи ошибок: `logs/errors.log` или `logs/django.log`
2. Определить задействованное представление/сервис
3. Добавить print/логирование для отладки
4. Запустить: `python manage.py runserver`
5. Написать тест-кейс
6. Закоммитить с четким сообщением

### Оптимизировать производительность
1. Проверить медленные запросы: `django-debug-toolbar` (добавить в settings)
2. Добавить индексы базы данных (в model Meta.indexes)
3. Использовать `select_related()` / `prefetch_related()`
4. Увеличить TTL кэша для стабильных данных
5. Использовать пагинацию для больших наборов данных

---

## Важные файлы для ознакомления

**Конфигурация:**
- `printer_inventory/settings.py` (23KB) - Вся конфигурация Django
- `.env` - Секреты, хосты, учетные данные
- `docker-compose.yml` - Keycloak для разработки

**Основная логика:**
- `inventory/services.py` (611 строк) - Движок опроса
- `inventory/web_parser.py` (18KB) - Веб-скрапинг
- `monthly_report/services_inventory_sync.py` (16KB) - Логика синхронизации

**Представления (модульные):**
- `inventory/views/printer_views.py` - CRUD операции
- `inventory/views/api_views.py` - JSON API
- `inventory/views/web_parser_views.py` - UI веб-парсинга
- `inventory/views/export_views.py` - Экспорт в Excel

**Админка и аутентификация:**
- `printer_inventory/auth_backends.py` (13KB) - Интеграция Keycloak
- `access/models.py` - Модель белого списка
- `access/middleware.py` - Контроль доступа на уровне приложения

**Асинхронная работа:**
- `inventory/tasks.py` - Celery задачи
- `monthly_report/signals.py` - Post-save хуки

**Frontend:**
- `templates/base.html` - Мастер-шаблон с Alpine.js
- `static/js/vendor/alpine.min.js` - Реактивный фреймворк
- `static/css/vendor/bootstrap.min.css` - CSS фреймворк

---

## Переменные окружения (обязательные)

```bash
# Django
SECRET_KEY=<случайная строка 50+ символов>
DEBUG=False (production)
USE_HTTPS=True (production)
ALLOWED_HOSTS=example.com,www.example.com

# База данных
DB_NAME=printer_inventory
DB_USER=postgres
DB_PASSWORD=<сильный пароль>
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=<опционально>

# Keycloak
KEYCLOAK_SERVER_URL=https://keycloak.example.com
KEYCLOAK_REALM=printer-inventory
OIDC_CLIENT_ID=<из Keycloak>
OIDC_CLIENT_SECRET=<из Keycloak>
OIDC_VERIFY_SSL=True

# GLPI Agent
GLPI_PATH=/usr/bin (Linux), /Applications/GLPI-Agent/bin (Mac), и т.д.
HTTP_CHECK=True (включить веб-парсинг)
POLL_INTERVAL_MINUTES=60
```

---

## Запуск команд

**Разработка:**
```bash
python manage.py runserver 0.0.0.0:8000        # Веб-сервер
celery -A printer_inventory worker              # Асинхронный worker (отдельный терминал)
celery -A printer_inventory beat                # Планировщик (отдельный терминал)
```

**Production:**
```bash
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application
./start_workers.sh                              # Запускает 3 worker + beat
```

**База данных:**
```bash
python manage.py migrate                        # Применить миграции
python manage.py makemigrations                 # Создать миграции
python manage.py createsuperuser                # Создать админ-пользователя
```

**Утилиты:**
```bash
python manage.py toggle_debug --status          # Проверить DEBUG
python manage.py cleanup_old_tasks              # Удалить старые опросы
python manage.py import_flask_db                # Импорт из legacy
python manage.py manage_whitelist --add username # Добавить пользователя
```

---

## Тестирование

```bash
python manage.py test                           # Запустить все тесты
python manage.py test inventory                 # Специфичные для приложения
python manage.py test --verbosity=2             # Подробный вывод
python manage.py test inventory.tests.TestPrinterModel --keepdb
```

---

## Советы по отладке

**Включить подробное логирование:**
- Установить `DEBUG=True` в разработке
- Проверить `logs/django.log` для исключений
- Проверить `logs/celery.log` для сбоев задач
- Проверить `logs/keycloak_auth.log` для проблем с аутентификацией

**Тестировать WebSockets:**
- Открыть консоль браузера: `const ws = new WebSocket('ws://localhost:5000/ws/inventory/')`
- Проверить группы: `redis-cli SMEMBERS inventory_updates`

**Мониторить Celery:**
```bash
python manage.py celery_monitor
# Или: celery -A printer_inventory inspect active
```

**Запросы к базе данных:**
- Добавить `print(str(query.query))` перед `.all()`
- Проверить медленные запросы в логах
- Использовать explain: `printer.objects.all().explain()`

---

## Чеклист развертывания

- [ ] Установить DEBUG=False
- [ ] Сгенерировать SECRET_KEY (50+ символов)
- [ ] Настроить PostgreSQL (план резервного копирования)
- [ ] Настроить Redis (с паролем)
- [ ] Настроить Keycloak realm и клиент
- [ ] Настроить CSRF origins
- [ ] Настроить SSL сертификаты
- [ ] Запустить миграции
- [ ] Собрать статические файлы
- [ ] Запустить Daphne + workers
- [ ] Настроить обратный прокси (nginx)
- [ ] Мониторить логи
- [ ] Добавить начальных пользователей в белый список
- [ ] Протестировать страницы ошибок (намеренная 500)
- [ ] Настроить стратегию резервного копирования

---

## Стиль кода и соглашения

- **Python**: PEP 8 (отступ 4 пробела)
- **Django**: Руководство по стилю Django (представления на основе классов, ModelForms)
- **Шаблоны**: Jinja2 с классами Bootstrap
- **Логирование**: logger = logging.getLogger(__name__)
- **Комментарии**: Объяснять ПОЧЕМУ, а не что (код самодокументируемый)

---

## Базовые показатели производительности

- Страница списка принтеров: <1с (с кэшированием)
- Один опрос: 2-5с (зависит от SNMP/веб ответа)
- Массовый импорт: 10с на 100 строк (Excel)
- WebSocket сообщение: <100мс (обновления в реальном времени)
- API ответ: <500мс (JSON эндпоинты)

---

## Чеклист безопасности

- [ ] Добавить пользователей в белый список в таблице AllowedUser
- [ ] Отключить Django admin в production (не используется с OIDC)
- [ ] Включить CSRF защиту (включена по умолчанию)
- [ ] Использовать HTTPS в production (USE_HTTPS=True)
- [ ] Ротировать SECRET_KEY в случае утечки
- [ ] Использовать сильный пароль базы данных
- [ ] Использовать пароль Redis (опционально, но рекомендуется)
- [ ] Мониторить логи на подозрительную активность
- [ ] Отключить DEBUG в production
- [ ] Тестировать страницы ошибок без раскрытия трассировок стека

---

## Полезные команды Django admin

```bash
# Инспектировать модели
python manage.py inspectdb

# Дамп данных
python manage.py dumpdata --indent 2 > data.json

# Загрузить данные
python manage.py loaddata data.json

# Сбросить миграции (ОПАСНО)
python manage.py migrate inventory zero

# Проверить базу данных
python manage.py dbshell

# Посмотреть установленные приложения
python manage.py debugsqlshell
```

---

## С чего начать (для новых разработчиков)

1. **Прочитать** `docs/CODEBASE_OVERVIEW.md` (вы здесь)
2. **Настроить** локальное окружение: `.env`, migrate, создать суперпользователя
3. **Изучить** приложение inventory: Models → Views → Templates
4. **Запустить** сервер разработки: `python manage.py runserver`
5. **Добавить** тестовый принтер через админку или UI
6. **Запустить** ручной опрос: Увидеть асинхронность в действии
7. **Проверить** логи: `logs/django.log`, `logs/celery.log`
8. **Читать** код: Начать с `inventory/services.py` (основная логика)
9. **Добавить** функцию: Следовать разделу "Добавить новую функцию" выше
10. **Развернуть**: Следовать чеклисту развертывания

---

## Контакты и поддержка

- Django Docs: https://docs.djangoproject.com/
- Celery Docs: https://docs.celeryproject.org/
- Channels: https://channels.readthedocs.io/
- Keycloak: https://www.keycloak.org/
- GLPI: https://github.com/glpi-project/glpi-agent
- PostgreSQL: https://www.postgresql.org/docs/

Для вопросов по кодовой базе, проверьте историю коммитов git:
```bash
git log --oneline | head -20                    # Последние коммиты
git show <commit> --stat                        # Что изменилось
git blame <file>                                # Кто что изменил
```

---

**Создано**: 2025-11-17
**Всего файлов**: 1 (QUICK_REFERENCE.md)
**Цель**: Быстрый поиск для разработчиков, работающих с этой кодовой базой
