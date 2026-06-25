по # Security TODO

Результаты ревью ветки `test-locust`. Критических уязвимостей не найдено,
но есть моменты, которые стоит подправить.

---

## 1. `_get_client_ip` — неправильный выбор IP из X-Forwarded-For

**Файл:** `printer_inventory/middleware.py:70-71`

```python
ips = [ip.strip() for ip in x_forwarded_for.split(",")]
return ips[-1] if ips else remote_addr  # <-- берёт ПОСЛЕДНИЙ IP
```

**Проблема:** формат XFF — `клиент, прокси1, прокси2`. `ips[-1]` возвращает
IP последнего прокси, а не клиента. Нужно `ips[0]`.

**Исправление:**
```python
return ips[0] if ips else remote_addr
```

**Серьёзность:** Низкая (используется только для логирования), но в логах
будет IP прокси вместо реального клиента.

---

## 2. SSRF — DNS rebinding обходит `_validate_printer_url`

**Файл:** `inventory/views/web_parser_views.py:21-52`

**Проблема:** для hostname проверяются только `localhost` и
`metadata.google.internal`. Атакующий может зарегистрировать домен
(например `evil.example.com`), который резолвится в `127.0.0.1`, и обойти
проверку.

**Исправление:** резолвить hostname через `socket.getaddrinfo()` и проверять
полученный IP-адрес:

```python
import socket

try:
    ip = ipaddress.ip_address(hostname)
except ValueError:
    # Это hostname — резолвим в IP
    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if resolved:
            resolved_ip = ipaddress.ip_address(resolved[0][4][0])
            if resolved_ip.is_loopback or resolved_ip.is_link_local:
                return False, f"Hostname {hostname} резолвится в запрещённый IP: {resolved_ip}"
    except socket.gaierror:
        return False, f"Не удалось разрешить hostname: {hostname}"
```

**Серьёзность:** Средняя. Эксплуатация требует права `manage_web_parsing`,
но позволяет сканировать внутренние сервисы через Selenium.

---

## 3. CI: Locust `--exit-code-on-error 0` игнорирует ошибки

**Файл:** `.github/workflows/lint.yml:192`

```yaml
--exit-code-on-error 0
```

**Проблема:** smoke-тест Locust никогда не провалит CI, даже если все
запросы вернут 500. Тест бесполезен.

**Исправление:** вернуть `--exit-code-on-error 1` после того, как тест
стабилизирован, или хотя бы поставить порог ошибок:

```yaml
--exit-code-on-error 1
```

---

## 4. Неотслеживаемые файлы — добавить в .gitignore

`git status` показывает:
```
dump.rdb
edgedriver_mac64_m1/
pip_packages.zip
printer_inventory/edgedriver_mac64_m1/
SECURITY_AUDIT.md
```

**Исправление:** добавить в `.gitignore`:
```gitignore
# Redis dump
dump.rdb

# Selenium drivers
edgedriver_mac64_m1/
printer_inventory/edgedriver_mac64_m1/

# Archives
*.zip
```

---

## 5. `reauth_complete` — нет проверки аутентификации

**Файл:** `printer_inventory/auth_views.py` (view `reauth_complete`)

**Проблема:** view в `OIDC_EXEMPT_URLS` и не требует `@login_required`.
Возвращает статичный HTML с `postMessage`. Сам по себе безопасен (проверка
`origin` в `session-manager.js`), но если в будущем туда добавят
пользовательские данные — станет XSS-вектором.

**Рекомендация:** добавить комментарий-предупреждение или `@login_required`,
если OIDC flow это позволяет.

---

## Что уже сделано хорошо (не трогать)

- Pickle serializer заменён на JSON (`settings.py`) — убран RCE-вектор
- `unsafe-eval` удалён из CSP
- Пароли proxy_page перенесены из GET-параметров в сессию
- Добавлена валидация IP/community перед `subprocess` (command injection)
- Добавлена санитизация serial_number при записи XML (path traversal)
- Open redirect закрыт через `url_has_allowed_host_and_scheme()`
- WebSocket consumers отклоняют анонимных пользователей
- `ALLOWED_RESET_FIELDS` whitelist в `api_reset_manual_flag`
- Claims логируются без токенов/секретов
- SECRET_KEY проверяется в production
