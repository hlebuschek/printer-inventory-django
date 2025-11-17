# Printer Inventory Django - Индекс документации

Эта директория содержит комплексную документацию по кодовой базе Printer Inventory Django, разработанную для AI-ассистентов и разработчиков, работающих над этим проектом.

## Файлы документации

### 1. **QUICK_REFERENCE.md** (Начните здесь!)
**Длина:** 439 строк | **Время чтения:** 10-15 минут
**Лучше всего для:** Быстрого поиска, начала работы, типичных задач

Краткий справочник с:
- Обзором проекта и ключевой статистикой
- Архитектурными паттернами с первого взгляда
- Диаграммой иерархии моделей
- 5 типичными задачами (добавить функцию, API, периодическую задачу, исправить баг, оптимизировать)
- Шпаргалкой по командам
- Чеклистом развертывания
- Советами по отладке

**Начните здесь:** Если вам нужно быстро разобраться

---

### 2. **CODEBASE_OVERVIEW.md** (Глубокое погружение)
**Длина:** 1,111 строк | **Время чтения:** 45-60 минут
**Лучше всего для:** Понимания архитектуры, подробного технического справочника

Комплексная техническая документация с:
- Полной структурой директорий (объяснено 400 файлов)
- Архитектурой Django приложений (inventory, contracts, access, monthly_report)
- Полным технологическим стеком (23 зависимости)
- Структурой конфигурации (settings, env vars, middleware, caching, Celery)
- Моделями баз данных и ER-диаграммами
- Маршрутизацией URL и API эндпоинтами
- Организацией представлений и шаблонов
- Сервисами и бизнес-логикой
- Аутентификацией и авторизацией
- WebSocket и функциями реального времени
- Настройкой тестирования и командами управления
- Рабочими процессами разработки и production
- Соображениями производительности
- Руководством по устранению неполадок
- Чеклистом развертывания

**Начните здесь:** Когда вам нужно понять, как все работает вместе

---

### 3. **ERROR_HANDLING.md** (Справочник)
**Длина:** 235 строк | **Время чтения:** 5-10 минут
**Лучше всего для:** Паттернов обработки ошибок, отладки

Документация по:
- Пользовательским страницам ошибок (400, 403, 404, 500)
- Системе логирования
- Тестированию обработчиков ошибок
- Типам ошибок и обработчикам

---

## Быстрая навигация

### По случаям использования

**Я AI-ассистент, с чего начать?**
1. Прочитать: QUICK_REFERENCE.md (15 мин)
2. Просмотреть: CODEBASE_OVERVIEW.md (15 мин)
3. Изучить: inventory/models.py и inventory/services.py
4. Задавать вопросы или начинать реализацию!

**Мне нужно добавить новую функцию**
1. Прочитать: QUICK_REFERENCE.md → "Типичные задачи для AI-помощников"
2. Посмотреть: inventory/models.py (паттерны моделей)
3. Посмотреть: inventory/views/printer_views.py (паттерны представлений)
4. Посмотреть: templates/base.html (паттерны frontend)
5. Следовать: Пошаговому руководству в QUICK_REFERENCE.md

**Мне нужно исправить баг**
1. Проверить: logs/django.log или logs/celery.log
2. Прочитать: "Советы по отладке" в QUICK_REFERENCE.md
3. Найти: Задействованное представление/сервис
4. Отладить: python manage.py runserver + добавить логирование
5. Протестировать: python manage.py test
6. Закоммитить: С понятным сообщением

**Мне нужно понять аутентификацию**
1. Прочитать: CODEBASE_OVERVIEW.md → "Аутентификация и авторизация"
2. Посмотреть: printer_inventory/auth_backends.py
3. Проверить: access/models.py (белый список AllowedUser)
4. Просмотреть: access/middleware.py (доступ на уровне приложения)

**Мне нужно развернуть это**
1. Прочитать: QUICK_REFERENCE.md → "Чеклист развертывания"
2. Следовать: Чеклисту из 15 пунктов
3. Использовать: CODEBASE_OVERVIEW.md → "Production развертывание"
4. Проверить: ERROR_HANDLING.md для страниц ошибок в prod

**Мне нужно понять асинхронные задачи**
1. Прочитать: CODEBASE_OVERVIEW.md → "Сервисы и бизнес-логика" → "inventory/tasks.py"
2. Посмотреть: inventory/tasks.py (определения задач)
3. Проверить: printer_inventory/settings.py → "Конфигурация CELERY"
4. Запустить: python manage.py celery_monitor

**Мне нужно понять WebSockets**
1. Прочитать: CODEBASE_OVERVIEW.md → "WebSockets и функции реального времени"
2. Посмотреть: inventory/consumers.py (определение потребителя)
3. Посмотреть: inventory/routing.py (маршрутизация WebSocket)
4. Проверить: printer_inventory/asgi.py (конфигурация ASGI)

---

## Краткий справочник по ключевым концепциям

### Четыре Django приложения

1. **inventory** - Основное управление принтерами
   - Модели: Printer, InventoryTask, PageCounter, WebParsingRule
   - Сервисы: SNMP опрос через GLPI, веб-парсинг
   - Асинхронность: Celery задачи для опроса
   - Реальное время: WebSockets для обновлений опросов

2. **contracts** - Отслеживание контрактов устройств
   - Модели: ContractDevice, DeviceModel, Cartridge
   - Функции: Импорт/экспорт Excel, связывание устройств
   - Интеграция: Связь с моделью Printer

3. **access** - Аутентификация и контроль доступа
   - Модель: AllowedUser (белый список Keycloak)
   - Аутентификация: OIDC через Keycloak
   - Middleware: Контроль доступа на уровне приложения

4. **monthly_report** - Отчетность о соответствии
   - Модель: MonthlyReport
   - Функции: Отслеживание счетчиков, метрики SLA (K1, K2)
   - Синхронизация: Периодически извлекает данные из inventory

### Основные рабочие процессы

**Процесс опроса:**
Пользователь/Планировщик → Celery задача → Сервис (GLPI или Web Parser) → InventoryTask/PageCounter → WebSocket обновление → Опциональная синхронизация в Monthly Report

**Процесс аутентификации:**
Keycloak OIDC → Проверка белого списка → Django User → Redis сессия → Контроль доступа к приложению

**Процесс отчетности:**
Импорт Excel → Строки MonthlyReport → Синхронизация из Inventory → Расчет метрик → Экспорт отчета

### Технологический стек с первого взгляда

- **Фреймворк:** Django 5.2 + Python 3.12
- **База данных:** PostgreSQL
- **Кэш:** Redis (сессии, кэширование, брокер Celery)
- **Асинхронность:** Celery (очередь задач) + Celery Beat (планировщик)
- **Сервер:** Daphne (ASGI для WebSockets)
- **Аутентификация:** Keycloak (OIDC провайдер)
- **Frontend:** Alpine.js + Bootstrap 5 + Chart.js
- **Опрос:** GLPI Agent (SNMP) + Selenium (веб-автоматизация)
- **Экспорт:** Excel (openpyxl) + Pandas

---

## Структура файлов

```
docs/
├── README.md (этот файл)
├── QUICK_REFERENCE.md (краткое руководство)
├── CODEBASE_OVERVIEW.md (комплексный справочник)
└── ERROR_HANDLING.md (паттерны обработки ошибок)

printer_inventory/
├── settings.py (23KB - вся конфигурация)
├── auth_backends.py (13KB - интеграция Keycloak)
├── middleware.py (безопасность и контроль доступа)
├── urls.py (корневая маршрутизация URL)
├── asgi.py (конфигурация WebSocket)
└── celery.py (конфигурация Celery)

inventory/ (Основное управление принтерами - 8,000 строк)
├── models.py (377 строк)
├── services.py (611 строк - ОСНОВНАЯ ЛОГИКА)
├── views/ (5 модульных файлов представлений)
├── tasks.py (Celery задачи)
├── web_parser.py (18KB - веб-скрейпинг)
├── admin.py (20KB - настройка админки)
└── management/commands/ (8 команд импорта/экспорта)

contracts/ (Контракты устройств)
├── models.py (10KB - 8 моделей)
├── views.py (33KB - 15+ CBV)
├── forms.py (11KB - 5 форм)
├── admin.py (23KB - UI админки)
└── management/commands/ (3 команды импорта)

access/ (Аутентификация)
├── models.py (белый список AllowedUser)
├── middleware.py (доступ на уровне приложения)
├── views.py (обработчики отказа в доступе)
└── management/commands/ (4 команды настройки)

monthly_report/ (Отчетность)
├── models.py (311 строк)
├── views.py (49KB - UI отчетности)
├── services_inventory_sync.py (16KB - логика синхронизации)
├── integrations/ (классы адаптеров)
└── management/commands/ (4 команды синхронизации)

templates/
├── base.html (основной шаблон с Alpine.js)
├── error.html (обработка ошибок)
├── registration/ (шаблоны входа)
└── [специфичные для приложений шаблоны]

static/
├── css/vendor/ (Bootstrap)
├── js/vendor/ (Alpine.js, Chart.js)
└── fonts/ (Bootstrap Icons)
```

---

## Самые важные файлы для ознакомления

### Обязательно прочитать (по порядку)
1. `printer_inventory/settings.py` - Вся конфигурация объяснена
2. `inventory/services.py` - Основная логика опроса
3. `inventory/models.py` - Модели данных
4. `printer_inventory/auth_backends.py` - Интеграция Keycloak

### Часто изменяемые
- `inventory/views/printer_views.py` - Изменения UI
- `inventory/services.py` - Логика опроса
- `templates/` - Изменения frontend
- `printer_inventory/settings.py` - Изменения конфигурации

### Справочные
- `inventory/utils.py` - Валидация и утилиты GLPI
- `monthly_report/services_inventory_sync.py` - Логика синхронизации
- `contracts/models.py` - Паттерны моделей устройств

---

## Рабочий процесс разработки

### Локальная настройка (5 мин)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
```

### Запуск в разработке (3 терминала)
```bash
# Терминал 1: Веб-сервер
python manage.py runserver 0.0.0.0:8000

# Терминал 2: Celery worker
celery -A printer_inventory worker --loglevel=INFO

# Терминал 3: Celery Beat (планировщик)
celery -A printer_inventory beat --loglevel=INFO
```

### Типичные команды
```bash
# Тестирование
python manage.py test
python manage.py test inventory --verbosity=2

# База данных
python manage.py migrate
python manage.py makemigrations

# Отладка
python manage.py toggle_debug --on
python manage.py test_errors --test-all

# Утилиты
python manage.py cleanup_old_tasks
python manage.py manage_whitelist --add username
```

### Production (1 команда на сервис)
```bash
# Веб-сервер
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application

# Workers
./start_workers.sh

# С обратным прокси (nginx/Apache)
# → прокси на 0.0.0.0:5000
```

---

## Получение помощи

### Логи для проверки
- `logs/django.log` - Ошибки и информация Django
- `logs/errors.log` - Только уровень ошибок
- `logs/celery.log` - Логи задач Celery
- `logs/keycloak_auth.log` - Отладка аутентификации
- `logs/redis.log` - Предупреждения Redis

### Команды отладки
```bash
# Проверка работоспособности системы
python manage.py api/system-status/

# Мониторинг Celery
python manage.py celery_monitor

# Диагностика демона
python manage.py diagnose_daemon

# Статистика Redis
redis-cli info
redis-cli SMEMBERS inventory_updates (группы WebSocket)
```

### История Git
```bash
git log --oneline | head -20
git show <commit> --stat
git blame <file>
```

---

## Чеклисты

### Чеклист перед коммитом
- [ ] Тесты пройдены: `python manage.py test`
- [ ] Нет ошибок в логах
- [ ] Код следует PEP 8
- [ ] Добавлены docstrings
- [ ] Обновлены модели/миграции
- [ ] Обновлена документация, если функция изменилась

### Чеклист развертывания
- [ ] DEBUG = False
- [ ] SECRET_KEY сгенерирован (50+ символов)
- [ ] PostgreSQL настроен
- [ ] Redis с паролем
- [ ] Настройка Keycloak realm/client
- [ ] CSRF origins настроены
- [ ] SSL сертификаты установлены
- [ ] Миграции запущены
- [ ] Статические файлы собраны
- [ ] Daphne + workers запущены
- [ ] Обратный прокси настроен
- [ ] Директория логов существует с правильными разрешениями
- [ ] Начальные пользователи в белом списке
- [ ] Страницы ошибок протестированы
- [ ] Резервное копирование настроено

---

## Ресурсы

### Официальная документация
- Django: https://docs.djangoproject.com/
- Celery: https://docs.celeryproject.org/
- Channels: https://channels.readthedocs.io/
- Keycloak: https://www.keycloak.org/documentation
- PostgreSQL: https://www.postgresql.org/docs/
- Redis: https://redis.io/documentation
- GLPI: https://github.com/glpi-project/glpi-agent

### Документация проекта
- См. ERROR_HANDLING.md для обработки ошибок
- См. CODEBASE_OVERVIEW.md для подробных технических деталей
- См. QUICK_REFERENCE.md для быстрых ответов
- Проверьте историю git: `git log --oneline`

---

## Об этой документации

**Создано:** 2025-11-17
**Всего строк:** 1,785 (в 3 файлах)
**Охват:** Полная структура кодовой базы, архитектура, технологический стек
**Целевая аудитория:** AI-ассистенты, новые разработчики, сопровождающие
**Назначение:** Комплексное введение и справочник для работы с кодовой базой

### Размеры файлов
- QUICK_REFERENCE.md: 439 строк (13 KB)
- CODEBASE_OVERVIEW.md: 1,111 строк (37 KB)
- ERROR_HANDLING.md: 235 строк (8.5 KB)
- README.md: Этот файл

---

## Контроль версий

```
Текущая ветка: claude/...
Основная ветка: (использовать для PR)
Коммиты: 25+ последних (Merge PR, fix, web_parser, sync, и т.д.)
```

---

## Вопросы?

Если у вас возникли вопросы при работе с этой кодовой базой:

1. **Вопрос о коде?** Проверьте соответствующий файл и прочитайте комментарии
2. **Вопрос об архитектуре?** См. CODEBASE_OVERVIEW.md
3. **Как мне...?** Проверьте QUICK_REFERENCE.md
4. **Ошибка?** Проверьте директорию logs/ и ERROR_HANDLING.md
5. **Все еще застряли?** Просмотрите структуру файлов и проследите поток

---

**Успешного кодирования! Документация - ваш друг.**
