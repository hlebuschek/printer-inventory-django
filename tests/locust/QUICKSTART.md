# Locust Load Testing - Быстрый старт

Этот гайд поможет вам запустить ваши первые нагрузочные тесты за 5 минут.

## Шаг 1: Установка зависимостей

```bash
pip install locust
```

## Шаг 2: Создание тестовых пользователей

Запустите скрипт для автоматического создания тестовых пользователей:

```bash
python tests/locust/setup_test_users.py
```

Этот скрипт создаст:
- **Django пользователя:** `locust_test` / `locust_password_123` (с правами на чтение inventory/contracts/monthly_report, запуск опроса и экспорт)
- **Keycloak whitelist:** для пользователя `user`

## Шаг 3: Запуск приложения

Убедитесь, что приложение запущено:

```bash
python manage.py runserver 0.0.0.0:8000
```

Или с поддержкой WebSocket:

```bash
python -m daphne -b 0.0.0.0 -p 8000 printer_inventory.asgi:application
```

## Шаг 4: Запуск Locust

Все команды выполняются из корня репозитория.

### Вариант A: С веб-интерфейсом (рекомендуется)

```bash
locust -f tests/locust/locustfile.py --host=http://localhost:8000
```

Откройте http://localhost:8089 в браузере и настройте:
- **Number of users:** 10
- **Spawn rate:** 2
- **Host:** http://localhost:8000

Нажмите "Start swarming" и наблюдайте за результатами!

### Вариант B: Быстрый тест без интерфейса

```bash
locust -f tests/locust/locustfile.py DjangoAuthUser \
    --host=http://localhost:8000 \
    --users 10 --spawn-rate 2 --run-time 1m \
    --headless --only-summary
```

### Вариант C: CI smoke-тест (только чтение, без опроса принтеров)

```bash
locust -f tests/locust/locustfile.py CISmokeUser \
    --host=http://localhost:8000 \
    --users 5 --spawn-rate 5 --run-time 30s \
    --headless --only-summary
```

## Шаг 5: Просмотр результатов

### В веб-интерфейсе:

1. Вкладка **Statistics** - общая статистика по запросам
2. Вкладка **Charts** - графики RPS, времени ответа
3. Вкладка **Failures** - список ошибок
4. Вкладка **Download Data** - экспорт результатов

### В командной строке:

В headless-режиме сводная таблица печатается в конце прогона.
Чтобы сохранить результаты в файлы, добавьте флаги:

```bash
--csv tests/locust/results/run --html tests/locust/results/report.html
```

## Доступные классы пользователей

| Класс | Что делает |
|-------|-----------|
| `DjangoAuthUser` | Все сценарии: inventory, API, контракты, отчёты. Ставит реальные опросы в очередь Celery! |
| `CISmokeUser` | Только чтение: API, контракты, отчёты. Безопасен для CI |
| `AnonymousUser` | Публичные страницы (логин, статика) без авторизации |

## Что дальше?

- Прочитайте полную документацию: `tests/locust/README.md`
- Настройте кастомные сценарии в `tests/locust/tasks/`
- Измените параметры в `tests/locust/locust.conf`

## Устранение проблем

### Login failed

Убедитесь, что тестовые пользователи созданы:

```bash
python tests/locust/setup_test_users.py --show
```

### Много 403 в статистике

У пользователя `locust_test` нет нужных прав — пересоздайте его:

```bash
python tests/locust/setup_test_users.py --django-only
```

### Connection refused

Проверьте, что приложение запущено:

```bash
curl http://localhost:8000/accounts/login/
```

### FileNotFoundError: .../logs/locust.log

`locust.conf` задаёт лог-файл относительным путём — запускайте locust
из корня репозитория (или создайте каталог `tests/locust/logs/`).

---

**Готово!** Теперь вы можете проводить нагрузочное тестирование вашего приложения.
