# CLAUDE.md — Printer Inventory Django

Django 5.2 + PostgreSQL + Redis + Celery + Channels + Keycloak/OIDC + Vue 3 + Vite + Bootstrap 5.
6 приложений: inventory, contracts, access, monthly_report, integrations, dashboard.

## Архитектура

**Сервисный слой:** бизнес-логика в `services.py`, НЕ в views. Главный файл — `inventory/services.py` (`run_inventory_for_printer()`).

**Celery:** 3 очереди (high_priority, low_priority, daemon). Конфиг — `printer_inventory/celery.py`.

**Redis DB:** 0=кэш (15мин), 1=сессии (7дн), 2=inventory (30мин), 3=Celery broker.

**WebSockets:** `/ws/inventory/` (обновления опросов), `/ws/monthly-report/<year>/<month>/` (совместное редактирование). Требует Daphne, не runserver.

**Фронтенд:** Vue 3 Composition API + Vite. В шаблонах `{% vite_asset %}` (НЕ `{% static %}`). Chart.js требует явный `Chart.register(...)`, canvas в DOM до `renderChart()`.

**Auth:** Keycloak OIDC → `AllowedUser` whitelist → группа "Наблюдатель" новым. `AjaxSessionRefreshMiddleware` для OIDC refresh в AJAX. Cookie: dev — `SameSite=Lax` + `localhost`; prod — `SameSite=None` + `Secure=True`.

**Код:** black + flake8, PEP 8, 120 символов. FBV для API, CBV для CRUD. `select_related()`/`prefetch_related()` обязательны.

## Ключевые файлы

| Файл | Что делает |
|------|-----------|
| `inventory/services.py` | Движок опроса (SNMP + Web), точка входа — `run_inventory_for_printer()` |
| `inventory/web_parser.py` | Веб-скрейпинг XPath + Regex |
| `inventory/utils.py` | `validate_against_history()` — валидация счетчиков, защита от Kyocera bug |
| `monthly_report/services_inventory_sync.py` | Синхронизация отчетов из inventory |
| `monthly_report/views.py` | Самый большой view (~2800 строк) |
| `printer_inventory/auth_backends.py` | OIDC backend + auto-refresh токенов |
| `printer_inventory/auth_views.py` | Login/logout/callback (CustomOIDCCallbackView) |
| `integrations/tasks.py` | Фоновые задачи GLPI/Okdesk |
| `printer_inventory/settings.py` | Вся конфигурация, middleware, installed apps |

## Модели данных

```
Organization
  ├── Printer (IP, SNMP community, polling_method, web credentials)
  │   ├── InventoryTask (история опросов, статус)
  │   │   └── PageCounter (счетчики, расходники)
  │   ├── WebParsingRule → WebParsingTemplate
  │   └── PrinterChangeLog
  └── ContractDevice ──OneToOne──→ Printer
      ├── DeviceModel (Manufacturer, City, ContractStatus)
      │   └── Cartridge (через DeviceModelCartridge M2M, is_primary)
      └── ContractStatus

MonthlyReport (sync из InventoryTask)
  ├── MonthControl (edit_until, is_published)
  ├── CounterChangeLog, BulkChangeLog

Integrations: GLPISync, IntegrationLog, GLPICrossCheck, OkdeskIssue
Access: AllowedUser, UserThemePreference, UserProfile, UserOkdeskToken, EntityChangeLog
```

**Неочевидно:** `MonthlyReport.organization` — CharField (не FK), совпадает с `Organization.name`. `Printer.model_display` возвращает `"{Manufacturer} {ModelName}"`, для только модели — `p.device_model.name`.

## Процесс опроса (ключевой workflow)

```
Триггер: кнопка → run_inventory_task_priority() [high_priority]
         Celery Beat XX:00 → inventory_daemon_task() [daemon]
         XX:55 → cleanup_queue_if_needed

Выполнение (inventory/services.py → run_inventory_for_printer):
  SNMP: GLPI Agent subprocess → парсинг XML → счетчики, расходники, serial, MAC
  WEB:  HTTP → WebParsingRule (XPath/Regex) → счетчики из HTML

Валидация (inventory/utils.py → validate_against_history):
  - Проверка исторических паттернов (A3, цвет)
  - Уменьшение счетчиков > 10% → отклонение
  - KYOCERA BUG: опрос < 24ч + скачок > 5000 стр → HISTORICAL_INCONSISTENCY
    (пропуск если > 30 дней без опроса)

Результат: InventoryTask + PageCounter (только при успехе)
           → WebSocket 'inventory_updates'
           → optional sync с monthly_report
```

## Celery Beat

| Задача | Когда | Очередь |
|--------|-------|---------|
| `cleanup_queue_if_needed` | XX:55 | daemon |
| `inventory_daemon_task` | XX:00 | daemon |
| `cleanup_old_inventory_data` | 03:00 | low_priority |
| `auto_link_devices_task` | 04:00 | low_priority |
| `check_all_devices_in_glpi` | 02:00 | high_priority |
| `cross_check_glpi_task` | 05:00 | low_priority |
| `sync_okdesk_issues` | */4:30 | low_priority |
| `sync_okdesk_issues` (full) | 03:00 | low_priority |

## Права доступа

Группы создаются через `python manage.py bootstrap_roles`.

**inventory:** `access_inventory_app`, `run_inventory`, `export_printers`, `export_amb_report`, `manage_web_parsing`, `view_web_parsing`, `can_create_public_templates`
**contracts:** `access_contracts_app`, `export_contracts`
**monthly_report:** `access_monthly_report`, `upload_monthly_report`, `edit_counters_start`, `edit_counters_end`, `sync_from_inventory`, `view_change_history`, `view_monthly_report_metrics`, `can_manage_month_visibility`, `can_reset_auto_polling`, `can_poll_all_printers`, `can_delete_month`, `override_auto_lock`
**dashboard:** `access_dashboard_app`
**integrations:** `view_okdesk_issues`, `create_okdesk_issue`, `manage_okdesk_token`
**access:** `view_entity_changes`

## Запуск

```bash
python manage.py runserver 0.0.0.0:8000          # WSGI (без WS)
python -m daphne -b 0.0.0.0 -p 5000 printer_inventory.asgi:application  # ASGI (с WS)
cd frontend && npm run dev                        # Vite HMR
celery -A printer_inventory worker --loglevel=info
celery -A printer_inventory beat --loglevel=info
./start_workers.sh                                # Production: 3 worker + beat
```

## Логи

`logs/django.log` (общие), `logs/errors.log` (production), `logs/celery.log`, `logs/keycloak_auth.log`

## Troubleshooting

- **WebSockets:** нужен Daphne + Redis
- **Chart.js не рендерится:** `Chart.register(...)` + canvas в DOM до `renderChart()` (после `loading.value = false` + `await nextTick()`)
- **OIDC:** проверить Keycloak, `OIDC_CLIENT_ID/SECRET`, `logs/keycloak_auth.log`
- **Dev cookies (Safari/Firefox):** использовать `localhost`, не `127.0.0.1`
