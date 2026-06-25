# Security Audit Report

**Project:** Printer Inventory Django
**Date:** 2026-03-29
**Auditor:** Claude Code (automated review)
**Scope:** Full project codebase (ветка `test-locust` vs `main`)
**Status:** Все 17 уязвимостей исправлены

---

## Оглавление

1. [Сводная таблица](#summary)
2. [Подробное описание уязвимостей и исправлений](#details)
3. [Чеклист перед деплоем на production](#checklist)
4. [Не вошло в отчёт (false positives)](#false-positives)

---

<a id="summary"></a>
## 1. Сводная таблица

| # | Severity | Категория | Файл(ы) | Статус |
|---|----------|-----------|----------|--------|
| 1 | **HIGH** | Command Injection | `inventory/services.py` | FIXED |
| 2 | **HIGH** | SSRF | `inventory/views/web_parser_views.py` | FIXED |
| 3 | **MEDIUM** | Sensitive Data Exposure | `printer_inventory/auth_views.py` | FIXED |
| 4 | **MEDIUM** | WebSocket Auth Bypass | `inventory/consumers.py`, `monthly_report/consumers.py` | FIXED |
| 5 | **MEDIUM** | Missing Authorization | `monthly_report/views.py` | FIXED |
| 6 | **MEDIUM** | XSS via v-html | `inventory/views/web_parser_views.py` (серверная часть) | FIXED |
| 7 | **MEDIUM** | Path Traversal | `inventory/services.py` | FIXED |
| 8 | **MEDIUM** | Pickle Deserialization RCE | `printer_inventory/settings.py` | FIXED |
| 9 | **MEDIUM** | IP Spoofing | `printer_inventory/middleware.py` | FIXED |
| 10 | **MEDIUM** | OIDC Claims Logging | `printer_inventory/auth_backends.py` | FIXED |
| 11 | **MEDIUM** | Weak CSP | `printer_inventory/middleware.py` | FIXED |
| 12 | **HIGH** | Mass Assignment | `monthly_report/views.py` | FIXED |
| 13 | **MEDIUM** | Authorization Bypass | `monthly_report/views.py` | FIXED |
| 14 | **MEDIUM** | Weak Default SECRET_KEY | `printer_inventory/settings.py` | FIXED |
| 15 | **MEDIUM** | Admin Exposes Tokens | `access/admin.py` | FIXED |
| 16 | **MEDIUM** | Credentials in GET Params | `inventory/views/web_parser_views.py`, `WebParserPage.vue` | FIXED |
| 17 | **LOW** | Test Endpoint in Production | `printer_inventory/urls.py` | FIXED |

---

<a id="details"></a>
## 2. Подробное описание уязвимостей и исправлений

---

### #1. Command Injection via IP и Community в GLPI subprocess

**Severity:** HIGH
**Файл:** `inventory/services.py`

**Что было:**
Команда GLPI строилась через f-string с прямой интерполяцией `ip` и `community`:
```python
base_cmd = f'"{executable}" --host {ip} -i --community {community} ...'
```
На Windows (`shell=True`) это позволяло полноценную shell-инъекцию. Значения приходили из пользовательского ввода (API `api_probe_serial`) и из полей модели `Printer`.

**Что сделали:**
1. Добавили две функции валидации:
   ```python
   def _validate_ip(ip: str) -> bool:
       return bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip))

   def _validate_community(community: str) -> bool:
       return bool(re.match(r"^[a-zA-Z0-9_\-]+$", community))
   ```
2. В `_build_glpi_command()` добавили вызов валидации с `raise ValueError` при некорректных данных
3. В `run_discovery_for_ip()` добавили валидацию IP с возвратом ошибки

**Что проверить:**
- Запустить ручной опрос принтера через UI -- должен работать как раньше
- Попробовать создать принтер с IP вида `192.168.1.1; echo test` -- должна быть ошибка валидации
- Проверить `api_probe_serial` через Postman с некорректным IP

---

### #2. SSRF через proxy_page, fetch_page и execute_action

**Severity:** HIGH
**Файл:** `inventory/views/web_parser_views.py`

**Что было:**
Три endpoint'а принимали произвольный URL от пользователя и делали серверный запрос без валидации. Это позволяло сканировать внутреннюю сеть, читать cloud metadata (`169.254.169.254`), обращаться к Redis/PostgreSQL.

**Что сделали:**
1. Добавили функцию `_validate_printer_url(url)` которая проверяет:
   - Схема только `http` или `https` (блокирует `file://`, `ftp://`)
   - Блокирует loopback-адреса (`127.0.0.0/8`)
   - Блокирует link-local (`169.254.0.0/16`) -- защита от утечки cloud credentials
   - Блокирует multicast-адреса
   - Блокирует hostname `localhost`
2. Применили валидацию ко всем трём endpoint'ам: `fetch_page`, `proxy_page`, `execute_action`
3. Заменили `str(e)` в error responses на generic сообщения (не раскрывают внутреннюю структуру)

**Что проверить:**
- Веб-парсинг: загрузка страницы принтера по реальному IP -- должно работать
- Попробовать URL `http://127.0.0.1:6379/` или `http://169.254.169.254/` -- должны быть заблокированы
- Попробовать `file:///etc/passwd` -- должна быть ошибка

---

### #3. Debug print() логирует OIDC-токены

**Severity:** MEDIUM
**Файл:** `printer_inventory/auth_views.py`

**Что было:**
`CustomOIDCCallbackView.get()` содержал ~20 безусловных `print()` (помеченных "SAFARI DEBUG"), которые выводили:
- `dict(request.GET)` -- содержит OIDC authorization code
- `dict(request.session.items())` -- содержит access/refresh tokens
- Полные данные сессии до и после аутентификации

Также `logger.info()` логировал полный `request.GET`.

**Что сделали:**
1. Удалили все `print()` statements
2. Удалили логирование `dict(request.GET)` и `dict(request.session.items())`
3. Заменили на минимальные `logger.debug()` вызовы (session_key, username, успех/ошибка)
4. Сохранили `logger.warning()` для ошибок OIDC callback (без деталей токенов)

**Что проверить:**
- Войти через Keycloak -- должно работать как раньше
- Проверить `logs/django.log` -- не должно быть OIDC codes и токенов
- Проверить что stdout (Docker logs) не содержит print() от auth

---

### #4. WebSocket consumers принимают анонимные соединения

**Severity:** MEDIUM
**Файлы:** `inventory/consumers.py`, `monthly_report/consumers.py`

**Что было:**
Оба consumer'а вызывали `self.accept()` без проверки аутентификации. Анонимный пользователь мог подключиться к WebSocket и получать все broadcast-сообщения: результаты опросов, IP-адреса принтеров, серийные номера, имена редакторов.

**Что сделали:**
В метод `connect()` обоих consumer'ов добавили проверку:
```python
user = self.scope.get("user")
if not user or user.is_anonymous:
    await self.close()
    return
```
Анонимные соединения теперь закрываются сразу.

**Что проверить:**
- Открыть страницу с опросом, запустить опрос -- WebSocket обновления должны приходить
- В DevTools браузера (неавторизованный) попробовать `new WebSocket('ws://host/ws/inventory/')` -- соединение должно закрыться
- Проверить real-time редактирование monthly_report -- должно работать для авторизованных

---

### #5. Отсутствует проверка прав на api_change_history

**Severity:** MEDIUM
**Файл:** `monthly_report/views.py`

**Что было:**
API endpoint `api_change_history` имел только `@login_required`, но не `@permission_required("monthly_report.view_change_history")`. Любой авторизованный пользователь мог получить полный аудит-лог, включая IP-адреса редакторов.

**Что сделали:**
Добавили декоратор:
```python
@permission_required("monthly_report.view_change_history", raise_exception=True)
```

**Что проверить:**
- Пользователь с правом `view_change_history` -- история должна открываться
- Пользователь без этого права -- должен получить 403
- Проверить что в группе "Ежемесячные отчёты — История" это право есть

---

### #6. XSS через v-html в WebParserPage

**Severity:** MEDIUM
**Файл:** `inventory/views/web_parser_views.py` (серверная часть)

**Что было:**
Массив `actionLog` рендерился через `v-html` во Vue. Данные приходили с сервера, где пользовательский ввод (`selector`, `xpath`, `var_name`, сообщения об ошибках) интерполировался без экранирования:
```python
action_log.append(f"Click: {selector}")
```

**Что сделали:**
Добавили `html.escape()` для всех пользовательских данных в `execute_action`:
- `selector`, `value` -- данные от действий click/input
- `xpath`, `var_name` -- данные от extract-действий
- Сообщения об ошибках -- заменены на generic текст

**Что проверить:**
- Веб-парсинг: выполнить действия (click, input, extract) -- лог должен отображаться корректно
- Попробовать XPath с HTML-тегами (например `<img onerror=alert(1)>`) -- должно отобразиться как текст, не как HTML

---

### #7. Path Traversal в XML-экспорте через serial_number

**Severity:** MEDIUM
**Файл:** `inventory/services.py`

**Что было:**
Имя файла XML-экспорта строилось из `printer.serial_number` без санитизации:
```python
xml_filename = f"{printer.serial_number}.xml"
```
Серийный номер мог содержать `../../etc/cron.d/backdoor` (от SNMP-ответа или пользовательского ввода).

**Что сделали:**
1. Санитизация серийного номера:
   ```python
   safe_serial = re.sub(r"[^a-zA-Z0-9_\-]", "_", printer.serial_number or "unknown")
   ```
2. Проверка что итоговый путь не выходит за пределы директории:
   ```python
   if not os.path.abspath(xml_filepath).startswith(os.path.abspath(xml_export_dir)):
       logger.error(f"Path traversal attempt: {printer.serial_number}")
       return
   ```

**Что проверить:**
- Запустить опрос принтера с XML-экспортом -- XML-файл должен создаваться корректно
- Проверить что спецсимволы в серийном номере заменяются на `_`

---

### #8. Pickle Deserialization в Redis Cache -- RCE

**Severity:** MEDIUM
**Файл:** `printer_inventory/settings.py`

**Что было:**
Redis cache использовал `PickleSerializer`. При доступе к Redis (открытый порт, SSRF, отсутствие пароля) атакующий мог записать вредоносный pickle-объект и получить RCE при десериализации.

**Что сделали:**
Заменили сериализатор:
```python
# Было:
"SERIALIZER": "django_redis.serializers.pickle.PickleSerializer",
# Стало:
"SERIALIZER": "django_redis.serializers.json.JSONSerializer",
```

**Что проверить:**
- **ВАЖНО:** После деплоя нужно очистить Redis cache (`redis-cli FLUSHDB` для DB 0 и DB 2), т.к. старые Pickle-данные не десериализуются JSON-сериализатором
- Проверить что кэширование работает: загрузить страницу списка принтеров, второй раз должна загрузиться быстрее
- Redis DB 1 (сессии) **не затронута** -- сессии используют свой serializer
- Если возникают ошибки десериализации в логах -- очистить соответствующую Redis DB

---

### #9. IP Spoofing через X-Forwarded-For

**Severity:** MEDIUM
**Файл:** `printer_inventory/middleware.py`

**Что было:**
Оба middleware (`ErrorHandlingMiddleware` и `RequestLoggingMiddleware`) слепо доверяли заголовку `X-Forwarded-For`, беря первый элемент. Атакующий мог подделать свой IP в логах и аудит-записях, отправив поддельный заголовок.

**Что сделали:**
1. Создали единую функцию `_get_client_ip(request)`:
   - По умолчанию использует `REMOTE_ADDR` (TCP-соединение, нельзя подделать)
   - `X-Forwarded-For` доверяется **только** если `REMOTE_ADDR` входит в `settings.TRUSTED_PROXY_IPS`
   - При наличии доверенного прокси берёт последний IP из цепочки (ближайший к прокси)
2. Оба метода `get_client_ip` заменены на вызов общей функции

**Что проверить:**
- Если используется reverse proxy (nginx): добавить IP прокси в `settings.py`:
  ```python
  TRUSTED_PROXY_IPS = {"127.0.0.1", "172.17.0.1"}  # IP вашего nginx/haproxy
  ```
- Если reverse proxy нет -- ничего настраивать не нужно, `REMOTE_ADDR` используется по умолчанию
- Проверить логи: IP-адреса должны отображаться корректно

---

### #10. Логирование полных OIDC claims (PII и секреты)

**Severity:** MEDIUM
**Файл:** `printer_inventory/auth_backends.py`

**Что было:**
Метод `log_all_claims` (116 строк) дампил весь JSON claims в `keycloak_auth.log`, включая `at_hash`, `session_state`, `sid`, `nonce`, email и другие PII/секретные данные. Вызывался при каждом логине и каждой проверке claims.

**Что сделали:**
1. Заменили полный дамп на фильтрацию через allowlist:
   ```python
   SAFE_CLAIMS_FIELDS = {
       "preferred_username", "sub", "email", "email_verified",
       "given_name", "family_name", "name",
       "groups", "roles", "realm_access", "resource_access",
       "group", "role", "authorities", "memberOf",
       "typ", "azp", "scope", "sid", "iss", "aud",
   }
   ```
2. Метод сокращён с 116 до ~20 строк
3. Логируются только ключи claims (для диагностики) и безопасные значения
4. Поиск ролей/групп упрощён до прямых обращений к известным полям

**Что проверить:**
- Войти через Keycloak -- вход должен работать
- Проверить `logs/keycloak_auth.log` -- должны быть username, roles, groups, но **не** токены и `at_hash`
- Если нужна отладка OIDC -- временно добавить поля в `SAFE_CLAIMS_FIELDS`

---

### #11. CSP разрешает unsafe-eval

**Severity:** MEDIUM
**Файл:** `printer_inventory/middleware.py`

**Что было:**
Content-Security-Policy содержал `'unsafe-eval'` в `script-src`, что позволяло выполнять `eval()` в браузере. Если найден XSS-вектор, CSP не блокировал исполнение скриптов.

**Что сделали:**
Убрали `'unsafe-eval'` из CSP:
```
# Было:
script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net;
# Стало:
script-src 'self' 'unsafe-inline' cdn.jsdelivr.net;
```

`'unsafe-inline'` оставлен -- он необходим для inline-скриптов Vue и Alpine.js. Полная миграция на nonce-based CSP потребует значительных изменений во frontend.

**Что проверить:**
- **ВАЖНО:** Проверить все страницы приложения в браузере, открыть DevTools → Console
- Если появляются ошибки `Refused to evaluate a string as JavaScript` -- значит какой-то скрипт использовал `eval()` и нужно его исправить или вернуть `unsafe-eval` для этой страницы
- Особое внимание: Chart.js, Vite HMR (dev-режим), сторонние библиотеки
- В dev-режиме (`DEBUG=True`) CSP не применяется, поэтому ошибки появятся только в production

---

### #12. Mass Assignment через setattr без allowlist

**Severity:** HIGH
**Файл:** `monthly_report/views.py`

**Что было:**
`api_reset_manual_flag` принимал `field_name` из POST body и проверял только `endswith("_end")`, затем использовал в `setattr()`. Можно было записать произвольные значения в любое поле модели, заканчивающееся на `_end`.

**Что сделали:**
Заменили проверку `endswith("_end")` на explicit allowlist:
```python
ALLOWED_RESET_FIELDS = {"a4_bw_end", "a4_color_end", "a3_bw_end", "a3_color_end"}
if field_name not in ALLOWED_RESET_FIELDS:
    return JsonResponse({"ok": False, "error": "Недопустимое поле"}, status=400)
```

**Что проверить:**
- Сброс автоопроса для каждого типа счётчика (A4 ч/б, A4 цвет, A3 ч/б, A3 цвет) -- должен работать
- Если в модели `MonthlyReport` появятся новые `*_end` поля -- добавить их в `ALLOWED_RESET_FIELDS`

---

### #13. Отсутствует проверка MonthControl.is_editable

**Severity:** MEDIUM
**Файл:** `monthly_report/views.py`

**Что было:**
`api_reset_manual_flag` не проверял `MonthControl.is_editable`. Пользователь с правом `can_reset_auto_polling` мог сбросить флаги и перезаписать счётчики для закрытых месяцев.

**Что сделали:**
Добавили проверку:
```python
mc = MonthControl.objects.filter(month=obj.month).first()
if mc and not mc.is_editable:
    return JsonResponse({"ok": False, "error": "Месяц закрыт для редактирования"}, status=403)
```

**Что проверить:**
- Закрыть месяц (снять `is_editable`) -- кнопка "Вернуть на автоопрос" должна возвращать ошибку
- Открыть месяц -- кнопка должна работать

---

### #14. Слабый дефолтный SECRET_KEY

**Severity:** MEDIUM
**Файл:** `printer_inventory/settings.py`

**Что было:**
```python
SECRET_KEY = os.getenv("SECRET_KEY", "REPLACE_ME_WITH_SECURE_KEY")
```
Если `.env` не задаёт `SECRET_KEY`, приложение работало с известным значением.

**Что сделали:**
Добавили проверку при старте в production:
```python
if not DEBUG and SECRET_KEY == "REPLACE_ME_WITH_SECURE_KEY":
    raise ImproperlyConfigured(
        "SECRET_KEY must be set via environment variable in production!"
    )
```
Приложение не запустится в production без настроенного SECRET_KEY.

**Что проверить:**
- Убедиться что в `.env` на production задан надёжный `SECRET_KEY`
- Если нет -- сгенерировать: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- **ВНИМАНИЕ:** Смена SECRET_KEY инвалидирует все текущие сессии (пользователи будут разлогинены) и зашифрованные Okdesk-токены (нужно ввести заново)

---

### #15. Django Admin отображает зашифрованные токены

**Severity:** MEDIUM
**Файл:** `access/admin.py`

**Что было:**
`UserOkdeskTokenAdmin` не скрывал поле `encrypted_token`. Любой staff-пользователь через Django Admin мог видеть зашифрованные токены и расшифровать их, зная SECRET_KEY.

**Что сделали:**
1. Добавили `exclude = ("encrypted_token",)` -- поле не отображается в форме
2. Ограничили изменение и удаление только суперпользователями:
   ```python
   def has_change_permission(self, request, obj=None):
       return request.user.is_superuser
   def has_delete_permission(self, request, obj=None):
       return request.user.is_superuser
   ```

**Что проверить:**
- Зайти в Django Admin под staff-пользователем -- `encrypted_token` не должен отображаться
- Обычный staff не должен видеть кнопки "Изменить" и "Удалить" для токенов

---

### #16. Credentials передаются в GET-параметрах proxy_page

**Severity:** MEDIUM
**Файлы:** `inventory/views/web_parser_views.py`, `frontend/src/components/inventory/WebParserPage.vue`

**Что было:**
`proxy_page` принимал `username` и `password` через GET-параметры. GET-параметры сохраняются в:
- Логах nginx/Apache
- Истории браузера
- Заголовках Referer при переходах
- Панели Network в DevTools

Фронтенд формировал URL: `/proxy-page/?url=...&username=admin&password=secret`

**Что сделали:**
1. **Backend:** `proxy_page` теперь читает credentials из сессии (`request.session["_proxy_auth"]`), а не из GET-параметров
2. **Backend:** `fetch_page` (POST-запрос) при успешной загрузке сохраняет credentials в сессию с привязкой к URL
3. **Backend:** `proxy_page` при чтении из сессии проверяет совпадение хоста URL (credentials не утекут на другой хост)
4. **Frontend:** убрана конкатенация `&username=...&password=...` в URL iframe

**Что проверить:**
- Веб-парсинг с аутентификацией (принтеры с login/password на веб-интерфейсе):
  1. Ввести URL, username, password
  2. Нажать "Загрузить"
  3. iframe должен отобразить страницу (credentials берутся из сессии)
- Проверить что в URL iframe нет username/password (DevTools → Network)
- Проверить что credentials не попадают в access log nginx

---

### #17. Тестовый endpoint доступен в production

**Severity:** LOW
**Файл:** `printer_inventory/urls.py`

**Что было:**
```python
path("test-alpine/", TemplateView.as_view(template_name="alpine_test.html")),
```
Зарегистрирован безусловно (без `if settings.DEBUG`), доступен без аутентификации.

**Что сделали:**
Удалили эту строку полностью. Если нужно -- добавить внутрь блока `if settings.DEBUG`.

**Что проверить:**
- `GET /test-alpine/` должен возвращать 404

---

<a id="checklist"></a>
## 3. Чеклист перед деплоем на production

### Обязательно (блокирует деплой)

- [ ] **SECRET_KEY задан в `.env`** -- приложение не запустится без него (fix #14)
- [ ] **Очистить Redis cache** -- после смены сериализатора с Pickle на JSON (fix #8):
  ```bash
  redis-cli -n 0 FLUSHDB   # Общий кэш
  redis-cli -n 2 FLUSHDB   # Кэш инвентаря
  # НЕ чистить DB 1 (сессии) -- они используют свой формат
  ```
- [ ] **Запустить миграции** -- `python manage.py migrate` (хотя новых миграций нет, для уверенности)
- [ ] **Пересобрать фронтенд** -- `npm run build` (изменён `WebParserPage.vue`, fix #16)
- [ ] **Собрать статику** -- `python manage.py collectstatic --noinput`

### Настройка инфраструктуры

- [ ] **Настроить `TRUSTED_PROXY_IPS`** (fix #9) -- если перед Django стоит nginx/haproxy:
  ```python
  # settings.py или .env
  TRUSTED_PROXY_IPS = {"127.0.0.1"}  # IP вашего reverse proxy
  ```
  Если reverse proxy нет -- ничего добавлять не нужно, REMOTE_ADDR используется по умолчанию.

- [ ] **Redis защищён паролем** -- рекомендуется (fix #8 снижает риск, но не устраняет полностью):
  ```bash
  # redis.conf
  requirepass your_strong_password
  bind 127.0.0.1
  ```

### Функциональное тестирование

После деплоя проверить основные сценарии:

- [ ] **Аутентификация Keycloak** -- вход/выход через OIDC работает (fixes #3, #10)
- [ ] **WebSocket обновления** -- запустить опрос, проверить real-time обновление в UI (fix #4)
- [ ] **Ручной опрос принтера** -- запустить для одного принтера через UI (fix #1)
- [ ] **Веб-парсинг** -- загрузить страницу принтера, выполнить действия (fixes #2, #6, #16)
- [ ] **Веб-парсинг с auth** -- если есть принтеры с login/password, проверить iframe (fix #16)
- [ ] **Monthly report** -- редактирование счётчиков, сброс автоопроса (fixes #5, #12, #13)
- [ ] **Monthly report для закрытого месяца** -- сброс должен быть запрещён (fix #13)
- [ ] **Django Admin** -- зайти как staff, проверить что `encrypted_token` не виден (fix #15)
- [ ] **CSP** -- открыть все основные страницы, проверить Console на ошибки CSP (fix #11):
  - Главная страница (список принтеров)
  - Страница контрактов
  - Monthly report
  - Dashboard (Chart.js)
  - Веб-парсинг
- [ ] **404 страница** -- `GET /test-alpine/` должна вернуть 404 (fix #17)

### Проверка логов

- [ ] Проверить `logs/keycloak_auth.log` -- нет токенов и `at_hash` (fix #10)
- [ ] Проверить `logs/django.log` -- нет OIDC authorization codes (fix #3)
- [ ] Проверить stdout/stderr (Docker logs) -- нет print() от auth (fix #3)
- [ ] Проверить nginx access log -- нет username/password в URL (fix #16)

### Откат при проблемах

Если после деплоя возникли критические проблемы:

1. **Ошибки десериализации Redis** -- `redis-cli -n 0 FLUSHDB && redis-cli -n 2 FLUSHDB`
2. **CSP блокирует скрипты** -- временно вернуть `'unsafe-eval'` в `middleware.py`:
   ```python
   "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net; "
   ```
3. **Iframe веб-парсинга не загружается** -- проверить что `fetch_page` вызывается перед `proxy_page` (credentials сохраняются в сессии при fetch)
4. **IP в логах показывает IP прокси** -- настроить `TRUSTED_PROXY_IPS` (см. выше)

---

<a id="false-positives"></a>
## 4. Не вошло в отчёт (false positives)

| Проверка | Почему не уязвимость |
|----------|---------------------|
| `\|safe` в шаблонах (8 мест) | Все передают `json.dumps()` от серверных словарей (permissions, initial_data). Не содержат пользовательский ввод |
| `mark_safe` в `vite_helpers.py` | Генерирует статические `<script>` теги из Vite manifest. Нет user input |
| `csrf_exempt` | Только на debug views (`DEBUG=True`) |
| `.extra()` в `contracts/views.py` | Использует параметризованные запросы (`params=[...]`) |
| `ET.parse()` | Парсит файлы сгенерированные GLPI agent. Python ETree не раскрывает external entities |
| `yaml.load` | Не используется в проекте |
| `pickle.loads` напрямую | Не используется (только через Redis serializer, покрыто #8) |
| `eval()` в `safe_eval_formula` | Тройная защита: allowlist символов + AST whitelist + пустые builtins |
| Okdesk API token в query params | Требование стороннего API. Server-to-server запрос, не попадает в браузер |
| Crypto KDF (SHA-256 от SECRET_KEY) | SECRET_KEY высокоэнтропийный env var. Не эксплуатируемо |
| IDOR в `access/views.py` | Все запросы корректно ограничены `user=request.user` |
| MEDIA_ROOT file serving | XML exports не обслуживаются через URL routes |
| `reauth_complete` без auth | Возвращает статический HTML с `postMessage`. X-Frame-Options: SAMEORIGIN. Low risk |
| `heartbeat` CSRF | Защищён стандартным Django CSRF middleware |
| openpyxl XXE | Современные версии openpyxl защищены от XXE по умолчанию |
