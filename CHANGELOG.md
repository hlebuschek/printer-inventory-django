# Changelog

Все важные изменения проекта документированы в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/).

---

## [Unreleased]

### В разработке
- Мобильная версия интерфейса
- TypeScript миграция
- Unit тесты для Vue компонентов

---

## [2.5.0] - 2026-03-25

### Добавлено

#### Интеграция с Okdesk
- **Просмотр заявок** по серийному номеру устройства
  - Модальное окно на странице `/contracts/` с историей заявок
  - Поиск с учётом того, что одна заявка может принадлежать нескольким устройствам
  - Импорт заявок из SQLite через `python manage.py import_okdesk_issues`
- **Создание заявок через API**
  - Форма в модалке с автозаполнением данных устройства (организация, город, адрес, модель, серийник, картриджи)
  - Отправка в Okdesk API с персональным токеном пользователя
  - Обработка ошибок сети/таймаутов с кнопкой «Повторить отправку»
  - Созданная заявка сразу сохраняется в БД и отображается в списке
- **Управление токенами Okdesk**
  - Модель `UserOkdeskToken` с шифрованием Fernet (AES) на основе SECRET_KEY
  - Vue-модалка для ввода токена через меню пользователя
  - Импорт токенов из CSV: `python manage.py import_okdesk_tokens tokens.csv`
- **Синхронизация заявок**
  - Celery-задача `sync_okdesk_issues` — обновление статусов каждые 4 часа
  - Отслеживание источника: import / created / sync
- **Права доступа Okdesk** (3 права, 2 группы)
  - `view_okdesk_issues` — просмотр заявок
  - `create_okdesk_issue` — создание заявок
  - `manage_okdesk_token` — управление токеном
  - Группа «Okdesk — Просмотр заявок» и «Okdesk — Оператор»
  - Интеграция с существующими группами Договоры

#### Дашборд
- Страница `/dashboard/` с аналитикой и графиками (Chart.js)
- Плавное обновление графиков без перерисовки
- Отчёт среднего количества напечатанных страниц за месяц

#### Кросс-проверка с GLPI
- Модель `GLPICrossCheck` для хранения результатов
- Проверка офлайн/неопрашиваемых устройств на наличие в GLPI

#### Сравнение состава отчётов между месяцами
- Аналитика изменений на карточках месяцев (`diff_ip_gained` / `diff_ip_lost`)
- Видна только пользователям с правом `view_monthly_report_metrics`

#### Тёмная тема
- Полная поддержка тёмной темы для всех компонентов
- Синхронизация темы между устройствами через API
- По умолчанию светлая тема
- Улучшена читаемость таблиц, аккордеонов, выпадающих списков в тёмной теме

#### Импорт принтеров из Excel
- Management-команда для импорта принтеров

#### Промежуточные переменные для веб-парсинга
- Возможность использовать промежуточные переменные в вычислениях правил

#### Страница прав доступа
- Страница `/permissions/` переписана на Vue.js

### Исправлено
- Фильтры сбрасывались при перезагрузке страницы
- Блокировка автоматически заполненных полей в monthly report
- Читаемость ячеек «Итого» в тёмной теме
- Правильный подсчёт типа изменения счётчика
- Дублирование логов
- Поле `comment` в choices было захардкожено как пустой массив
- Кнопка истории изменений видна только с правами
- Миграция `0010` для корректной работы на чистой БД

### База данных
- Модель `OkdeskIssue` с индексами
- Модель `UserOkdeskToken` с шифрованием
- Модель `GLPICrossCheck`
- Права доступа для Okdesk

### Зависимости
- Добавлен пакет `cryptography` для шифрования токенов

### Переменные окружения (новые)
```bash
OKDESK_API_TOKEN=системный_токен_для_синхронизации
OKDESK_API_URL=https://abikom.okdesk.ru/api/v1  # по умолчанию
```

### Офлайн-установка пакетов (для сервера без интернета)
```bash
# На машине с интернетом:
docker build -f Dockerfile.pip-download --platform linux/amd64 -t pip-download .
docker run --rm -v $(pwd)/pip_packages:/out pip-download sh -c "cp /packages/* /out/"

# На сервере:
pip install --no-index --find-links=pip_packages -r requirements.txt
```

---

## [2.2.0] - 2025-11-22

### Добавлено

#### Фиксированная шапка таблицы Monthly Report
- **Удалена групповая шапка** таблицы ("Счётчики A4", "Счётчики A3")
  - Не предоставляла ценности и отображалась некорректно при скрытии столбцов
- **Реализована фиксированная шапка** через JavaScript клонирование
  - Шапка остаётся видимой при прокрутке страницы вниз
  - Позиционируется под navbar сайта с `position: fixed`
  - Точное копирование ширины столбцов через `getBoundingClientRect()`
  - Автоматическая синхронизация горизонтального скролла
- **Исправлен navbar** - больше не двигается при горизонтальной прокрутке таблицы
  - `position: fixed` для navbar
  - `overflow-x: hidden` для body
  - `margin-top: 56px` для главного контейнера

#### Автоматическая аутентификация через Keycloak
- **Автоматический редирект** на Keycloak для неавторизованных пользователей
  - При доступе к защищённой странице автоматическое перенаправление на Keycloak
  - Сохранение исходного URL для редиректа после входа
  - Показ Django формы логина с toast сообщением при ошибке Keycloak
- **Автоматическое назначение прав** новым пользователям
  - Группа "Наблюдатель" назначается автоматически при первом входе через Keycloak
  - Исправлен метод `update_user()` для вызова `assign_default_groups()`
- **Улучшенная обработка ошибок**
  - Редирект на страницу входа вместо 403 ошибки
  - Toast уведомления об ошибках аутентификации
  - Подробные сообщения об ошибках в логах

#### Возможность выбора способа входа после logout
- **Параметр `?manual=1`** для ручного выбора способа входа
  - Предотвращает автоматический редирект на Keycloak после logout
  - Позволяет переключаться между учётными записями
- **Кастомный `custom_logout()` view**
  - Корректный выход из Django сессии
  - Показ сообщения "Вы успешно вышли из системы"
  - Редирект на страницу выбора способа входа
- Пользователь может выбрать:
  - Войти через Keycloak (возможно с другой учётной записью)
  - Войти через Django логин/пароль
  - Просто закрыть страницу

#### Отслеживание наличия сетевого порта у моделей оборудования
- **Новое поле `has_network_port`** в модели `DeviceModel`
  - Boolean поле с индексом для быстрого поиска
  - По умолчанию `False`
  - Доступно в Django Admin для редактирования
- **Отображение в Django Admin**
  - Колонка "Сетевой порт" с визуальными индикаторами
  - Да (зеленым) / Нет (серым)
  - Фильтр по наличию сетевого порта
  - Поддержка сортировки
- **Management команда `populate_network_port`**
  - Автоматическое заполнение поля на основе данных из inventory
  - Если модель найдена в `Printer` (опрос), значит имеет сетевой порт
  - Режим dry-run для предпросмотра изменений
  - Фильтрация по производителю
  - Детальный вывод с опцией `--verbose`
- **Использование:**
  ```bash
  # Предпросмотр изменений
  python manage.py populate_network_port --dry-run

  # Применить автозаполнение
  python manage.py populate_network_port

  # Только для конкретного производителя
  python manage.py populate_network_port --manufacturer "HP"
  ```
- Позволяет в будущем анализировать, сколько устройств с сетевыми портами подключено к сети

### Исправлено

#### Проблемы с OIDC сессиями
- **Исправлен бесконечный цикл редиректов** при Keycloak аутентификации
  - Переопределён метод `get()` в `CustomOIDCCallbackView` вместо `login_success()`
  - Убраны дублирующие вызовы `auth_login()`
  - Родительский класс `OIDCAuthenticationCallbackView` уже вызывает `auth_login()`
- **Настроена передача cookie** при редиректах
  - Добавлена настройка `SESSION_COOKIE_SAMESITE = 'Lax'`
  - Сессия корректно сохраняется и передаётся между запросами
- **Исправлено сохранение `next` URL** для редиректа после входа
  - URL сохраняется в сессии как `oidc_login_next`
  - Корректная очистка из сессии после использования
  - Проверка безопасности URL (предотвращение внешних редиректов)

### Затронутые файлы
- `frontend/src/components/monthly-report/MonthReportTable.vue`
- `monthly_report/templates/monthly_report/month_detail_vue.html`
- `printer_inventory/auth_views.py`
- `printer_inventory/auth_backends.py`
- `printer_inventory/settings.py`
- `printer_inventory/urls.py`
- `monthly_report/views.py`
- `contracts/views.py`
- `contracts/models.py`
- `contracts/admin.py`
- `contracts/api_views.py`
- `contracts/migrations/0005_devicemodel_has_network_port.py`
- `contracts/management/commands/populate_network_port.py`
- `templates/registration/login_choice.html`

---

## [2.1.0] - 2025-11-21

### Добавлено

#### Система кастомных прав доступа
- **3 новых права для Monthly Report:**
  - `can_manage_month_visibility` - управление видимостью месяцев (публикация/скрытие)
  - `can_reset_auto_polling` - возврат принтера на автоматический опрос
  - `can_poll_all_printers` - запуск массового опроса всех принтеров
- **11 групп прав для детального управления доступом:**
  - Просмотр, Загрузка, Редакторы (начало/конец/полные)
  - Синхронизация, Менеджеры, История
  - Управление видимостью, Сброс автоопроса, Опрос всех принтеров
- Команда `python manage.py init_monthly_report_roles` для создания групп

#### Скрытые/опубликованные отчеты
- Новое поле `is_published` в модели `MonthControl`
- Отчеты по умолчанию создаются скрытыми для проверки
- Публикация через кнопку в интерфейсе (только для пользователей с правом)
- Наблюдатели не видят неопубликованные отчеты
- Чекбокс при загрузке Excel для выбора статуса публикации

#### Возврат на автоопрос
- Кнопка "Вернуть на автоопрос" на странице истории изменений
- Сброс всех флагов `manual_edit_*` для устройства
- Автоматическое восстановление значений из inventory
- Логирование в историю изменений

#### UI/UX улучшения
- Модальное окно принтера: кнопки перенесены в `modal-footer`
- Столбцы по умолчанию для первого визита страницы inventory
- Исправлена нумерация строк в таблице contracts с учетом пагинации
- Передача inventory permissions на страницу contracts для модального окна

### Исправлено
- Права inventory теперь передаются в contracts для редактирования принтеров
- Пустой массив столбцов в localStorage больше не приводит к пустой таблице
- Номера строк в contracts теперь непрерывны на всех страницах
- Страница `/permissions/` теперь отображает все новые права

### Документация
- Обновлен CLAUDE.md с информацией о новых правах и группах
- Добавлен раздел "Кастомные права доступа"
- Обновлены рабочие процессы для monthly_report
- Документирована модель MonthControl

### База данных
- Миграция `0007_add_custom_permissions.py` для новых прав
- Миграция `0006_monthcontrol_is_published.py` для публикации отчетов

---

## [2.0.0] - 2025-11-18

### Добавлено

#### Monthly Report - Полная миграция на Vue.js

**Компоненты:**
- `MonthListPage.vue` - список месяцев с карточками и фильтрацией
- `MonthDetailPage.vue` - детальная страница с таблицей отчёта
- `MonthReportTable.vue` - таблица с inline редактированием
- `UploadExcelPage.vue` - загрузка данных из Excel
- `ChangeHistoryPage.vue` - история изменений с откатом

**Функциональность:**
- Inline редактирование счётчиков с auto-save и debounce
- Трёхуровневая система permissions (user + duplicates + model specs)
- Двухуровневая система обнаружения аномалий:
  - Высокие значения (>10000) - красная подсветка
  - Исторические аномалии (среднее + 2000) - жёлтая подсветка
- Floating scrollbar внизу viewport для улучшения UX
- Toast уведомления с детальной статистикой
- Экспорт в Excel
- Синхронизация из inventory с детальной статистикой
- История изменений с возможностью отката

**API Endpoints:**
- `GET /monthly-report/api/months/` - список месяцев
- `GET /monthly-report/api/month/<year>/<month>/` - детали месяца
- `POST /monthly-report/api/update-counters/<pk>/` - обновление счётчиков
- `POST /monthly-report/api/sync/<year>/<month>/` - синхронизация
- `GET /monthly-report/api/change-history/<pk>/` - история изменений
- `POST /monthly-report/api/revert-change/<id>/` - откат изменения

**Документация:**
- `docs/MONTHLY_REPORT_VUE.md` - полная документация по Vue компонентам
- `docs/VUE_MIGRATION_COMPLETE.md` - обновлён статус миграции

### Исправлено

- Исправлена ошибка 500 в API истории изменений (field → field_name)
- Исправлена обработка загрузки Excel (теперь возвращает JSON с результатом)
- Исправлена интеграция Bootstrap modal (использование глобального объекта)
- Исправлена обработка аномалий (проверка объекта anomaly_info)
- Улучшена валидация форм с детальными сообщениями об ошибках

### Изменено

**Backend:**
- `monthly_report/views.py`:
  - Все views переключены на Vue шаблоны (*_vue.html)
  - Добавлен `api_change_history()` endpoint
  - `upload_excel()` теперь возвращает JSON вместо HTML
  - `api_month_detail()` возвращает ui_allow_* флаги для permissions
  - Улучшена обработка ошибок в API endpoints

**Frontend:**
- `frontend/src/main.js`:
  - Зарегистрированы 5 новых компонентов monthly_report
  - Добавлен параметр `reportId` в propsData
  - Улучшена передача данных через data-атрибуты

**Templates:**
- Созданы новые Vue шаблоны:
  - `month_list_vue.html`
  - `month_detail_vue.html`
  - `upload_vue.html`
  - `change_history_vue.html`

### Статистика

- **Компонентов создано:** 5
- **Строк кода (Vue):** ~2100
- **API endpoints:** 6 новых
- **Файлов изменено:** 15+
- **Коммитов:** 8
- **Время разработки:** ~8 часов

---

## [1.5.0] - 2025-11-17

### Добавлено

#### Vue.js Infrastructure

**Базовая инфраструктура:**
- Vue 3.4.15 + Composition API
- Vite 5.0.11 для сборки и hot reload
- Pinia 2.1.7 для state management
- Chart.js + vue-chartjs для графиков

**Архитектура:**
```
frontend/src/
├── components/
│   ├── PrinterInventoryApp.vue    # Тестовый компонент
│   ├── inventory/                 # Inventory компоненты
│   ├── contracts/                 # Contract компоненты
│   └── common/                    # Общие компоненты
├── composables/                   # Переиспользуемая логика
├── stores/                        # Pinia stores
├── utils/                         # Утилиты
└── main.js                        # Entry point
```

**Интеграция с Django:**
- Vite helpers (`printer_inventory/vite_helpers.py`)
- Template tags для Vite assets
- CSRF token передача
- Permissions через data-атрибуты

#### Inventory - Частичная миграция

**Компоненты:**
- `PrinterListPage.vue` - управление принтерами
- `PrinterForm.vue` - форма добавления/редактирования
- `WebParserPage.vue` - правила веб-парсинга
- `AmbExportPage.vue` - экспорт в формат AMB

#### Contracts

**Компоненты:**
- `ContractDeviceListPage.vue` - управление устройствами по договорам

### Исправлено

- URL prefix изменён с `/printers/` на `/inventory/`
- WhiteNoise отключен в DEBUG режиме
- Static files корректно отдаются в dev режиме
- CSRF токены передаются в Vue компоненты

### Документация

- `docs/VUE_MIGRATION_COMPLETE.md` - статус миграции
- `frontend/README.md` - руководство по фронтенду
- `CLAUDE.md` - обновлён с информацией о Vue.js

---

## [1.0.0] - 2025-11-01

### Добавлено

#### Базовый функционал

- **CRUD для принтеров** - добавление, редактирование, удаление
- **Inventory polling** - опрос через SNMP и HTTP
- **Multithreaded bulk polling** - массовый опрос с APScheduler
- **Real-time updates** - WebSockets через Django Channels
- **Импорт данных** - миграция из Flask SQLite БД

#### Django Apps

**inventory:**
- Модели: Printer, InventoryTask, PageCounter, WebParsingRule
- Views: CRUD, polling, export
- Services: SNMP polling, web parsing, Excel export

**contracts:**
- Модели: DeviceModel, ContractDevice, Cartridge
- Views: device management, import from Excel

**monthly_report:**
- Модели: MonthlyReport, CounterChangeLog, MonthControl
- Views: month list, detail, upload, history
- Services: audit, inventory sync

**access:**
- Модели: AllowedUser
- Auth: Keycloak OIDC integration
- Middleware: permissions checking

#### Инфраструктура

- **Django 5.2** - веб-фреймворк
- **PostgreSQL** - основная БД
- **Redis** - кэш и сессии (3 БД)
- **Celery** - асинхронные задачи
- **Django Channels** - WebSockets
- **Keycloak** - SSO/OIDC аутентификация

### Настроено

**Security:**
- CSRF protection
- Security headers
- Custom error pages (400, 403, 404, 405, 500)
- Logging system

**Development:**
- Debug toolbar
- Error testing tools
- Management commands

**Production:**
- WhiteNoise для static files
- Daphne ASGI server
- Celery workers
- Logging to files

### Документация

- `README.md` - основная документация
- `docs/ERROR_HANDLING.md` - обработка ошибок
- `docs/CODEBASE_OVERVIEW.md` - обзор кодовой базы
- `docs/QUICK_REFERENCE.md` - краткая справка
- `CLAUDE.md` - руководство для AI ассистентов

---

## Типы изменений

- **Добавлено** - новая функциональность
- **Изменено** - изменения в существующей функциональности
- **Устарело** - функциональность, которая скоро будет удалена
- **Удалено** - удалённая функциональность
- **Исправлено** - исправления багов
- **Безопасность** - изменения, связанные с безопасностью

---

## Ссылки

- [Vue.js 3 Docs](https://vuejs.org/)
- [Vite Docs](https://vitejs.dev/)
- [Django Docs](https://docs.djangoproject.com/)
- [Pinia Docs](https://pinia.vuejs.org/)
- [Bootstrap 5 Docs](https://getbootstrap.com/)
