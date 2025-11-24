# Решение проблемы Safari с Keycloak аутентификацией

## Проблема

Safari блокирует cookies при OAuth/OIDC редиректах между разными доменами из-за политики ITP (Intelligent Tracking Prevention). Симптомы:

- Firefox и Chrome работают нормально ✅
- Safari показывает бесконечный цикл редиректов ❌
- В логах: `Session key BEFORE: None`, `Cookies: []` ❌

## Причина

Safari считает `localhost` и `127.0.0.1` **разными доменами**. Если Django на `localhost:8000`, а Keycloak на `127.0.0.1:8080` (или наоборот), Safari блокирует cookies.

## Решение для Development

### 1. Используйте localhost для ОБОИХ сервисов

**Django:**
```bash
python -m daphne -b 0.0.0.0 -p 8000 printer_inventory.asgi:application
# Затем открывайте http://localhost:8000 (НЕ http://127.0.0.1:8000)
```

**Keycloak:**
Проверьте, что используется `localhost`:
```bash
export KEYCLOAK_SERVER_URL=http://localhost:8080
```

Или создайте `.env` файл:
```bash
KEYCLOAK_SERVER_URL=http://localhost:8080
OIDC_CLIENT_ID=printer-inventory-client
OIDC_CLIENT_SECRET=your-secret-here
```

### 2. Настройте Valid Redirect URIs в Keycloak

1. Откройте Keycloak Admin Console: `http://localhost:8080/admin`
2. Войдите с admin credentials
3. Выберите realm `printer-inventory`
4. Перейдите в **Clients** → `printer-inventory-client`
5. Добавьте в **Valid Redirect URIs**:
   ```
   http://localhost:8000/*
   ```
6. Добавьте в **Valid Post Logout Redirect URIs**:
   ```
   http://localhost:8000/*
   ```
7. Установите **Web Origins**:
   ```
   http://localhost:8000
   ```
8. Нажмите **Save**

### 3. Очистите cookies в Safari

```
Safari → Разработка → Очистить кэш
Safari → Разработка → Очистить cookie
```

Или используйте **Private Window** для тестирования.

### 4. Перезапустите Daphne

```bash
# Остановите текущий процесс (Ctrl+C)
python -m daphne -b 0.0.0.0 -p 8000 printer_inventory.asgi:application
```

### 5. Откройте Safari

```
http://localhost:8000
```

**НЕ** используйте `http://127.0.0.1:8000`!

## Решение для Production

В production используется другой подход, так как домены могут быть разными (например, `app.company.com` и `auth.company.com`).

### Автоматическая настройка

Установите переменную окружения:
```bash
USE_HTTPS=True
```

Это автоматически настроит:
```python
SESSION_COOKIE_SAMESITE = 'None'  # Разрешает cross-site cookies
SESSION_COOKIE_SECURE = True      # Требует HTTPS
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
```

### Требования для Production

1. **HTTPS обязателен!** SameSite=None не работает по HTTP
2. SSL сертификаты должны быть установлены
3. В Keycloak Valid Redirect URIs используйте HTTPS URL:
   ```
   https://your-domain.com/*
   ```
4. Установите переменные окружения:
   ```bash
   USE_HTTPS=True
   BASE_URL=https://your-domain.com
   KEYCLOAK_SERVER_URL=https://auth.your-domain.com
   CSRF_TRUSTED_ORIGINS=https://your-domain.com
   ```

## Диагностика

При входе через Safari в консоли должно появиться:

```
================================================================================
SAFARI DEBUG: OIDC Callback Called
================================================================================
GET params: {...}
Session key BEFORE: <some-key>
Session items BEFORE: {...}
Cookies: ['printer_inventory_sessionid', 'csrftoken']  ← Должны быть!
User Agent: ...Safari...
================================================================================
```

**Если `Cookies: []`** - значит Safari блокирует cookies. Проверьте:
1. Используете ли `localhost` для обоих сервисов (не `127.0.0.1`)
2. Настроены ли Valid Redirect URIs в Keycloak
3. Очищены ли старые cookies

## Дополнительная информация

### Почему это происходит?

Safari имеет политику ITP (Intelligent Tracking Prevention), которая блокирует третьесторонние cookies для защиты от трекинга. При OAuth редиректе:

1. Пользователь на `localhost:8000` (Django)
2. Редирект на `127.0.0.1:8080` (Keycloak)
3. Редирект обратно на `localhost:8000` (Django)

Safari видит `localhost` ≠ `127.0.0.1` и блокирует cookies как "third-party".

### SameSite атрибуты

- **`Lax`** - cookies отправляются при навигации (GET запросы), но не при AJAX cross-site
- **`Strict`** - cookies НИКОГДА не отправляются при cross-site запросах
- **`None`** - cookies отправляются всегда, НО требует `Secure=True` (HTTPS)

В development используем `Lax` (HTTP), в production `None` (HTTPS).

### Проверка настроек

```bash
# Проверить текущие настройки Django
python manage.py shell
>>> from django.conf import settings
>>> settings.SESSION_COOKIE_SAMESITE
>>> settings.SESSION_COOKIE_SECURE
>>> settings.USE_HTTPS
```

## Troubleshooting

**Проблема:** Safari всё ещё не пускает после настройки

**Решение:**
1. Полностью закройте Safari и откройте заново
2. Используйте Private Window
3. Проверьте Safari → Настройки → Конфиденциальность → отключите "Предотвращать перекрёстное отслеживание" (только для тестирования!)
4. Проверьте логи - должно быть `Cookies: ['printer_inventory_sessionid', ...]`

**Проблема:** В production не работает с разными доменами

**Решение:**
1. Убедитесь что `USE_HTTPS=True`
2. Проверьте что используется HTTPS (не HTTP)
3. Проверьте SSL сертификаты
4. Добавьте домены в `CSRF_TRUSTED_ORIGINS`

---

**Документация обновлена:** 2025-11-22
**Актуально для:** Safari 18.x, Django 5.2, Keycloak 23.x
