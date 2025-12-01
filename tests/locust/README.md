# Locust Load Testing для Printer Inventory Django

Комплексное нагрузочное тестирование веб-приложения управления инвентаризацией принтеров с использованием [Locust](https://locust.io/).

## Содержание

- [Возможности](#возможности)
- [Быстрый старт](#быстрый-старт)
- [Подготовка](#подготовка)
- [Сценарии тестирования](#сценарии-тестирования)
- [Запуск тестов](#запуск-тестов)
- [Результаты и метрики](#результаты-и-метрики)
- [Устранение неполадок](#устранение-неполадок)

---

## Возможности

✅ **Два способа авторизации:**
- Django стандартная форма (`DjangoAuthUser`)
- Keycloak OIDC flow (`KeycloakAuthUser`)

✅ **Комплексное тестирование:**
- Инвентаризация принтеров (просмотр, редактирование, опрос)
- API endpoints (REST API)
- Управление контрактами
- Месячные отчеты

✅ **Реалистичные сценарии:**
- Смешанные типы пользователей
- Анонимные пользователи
- Различные паттерны поведения

✅ **Детальная статистика:**
- Время ответа
- Количество запросов
- Процент ошибок
- Выявление медленных запросов

---

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install locust
```

### 2. Создание тестового пользователя

**Для Django авторизации:**

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from access.models import AllowedUser

# Создаем Django пользователя
user = User.objects.create_user('locust_test', password='locust_password_123')

# Добавляем в whitelist
AllowedUser.objects.create(
    username='locust_test',
    is_active=True,
    full_name='Locust Test User',
    notes='Тестовый пользователь для нагрузочного тестирования'
)
```

**Для Keycloak авторизации:**

```bash
python manage.py shell
```

```python
from access.models import AllowedUser

# Добавляем Keycloak пользователя в whitelist
AllowedUser.objects.create(
    username='user',  # Имя пользователя в Keycloak
    is_active=True,
    full_name='Keycloak Test User'
)
```

### 3. Запуск тестов

**С веб-интерфейсом (рекомендуется для первого раза):**

```bash
locust -f locustfile.py --host=http://localhost:8000
```

Откройте http://localhost:8089 в браузере.

**Без веб-интерфейса (headless):**

```bash
locust -f locustfile.py \
    --host=http://localhost:8000 \
    --users 10 \
    --spawn-rate 2 \
    --run-time 1m \
    --headless
```

---

## Подготовка

### Требования

1. **Запущенное приложение:**
   ```bash
   python manage.py runserver 0.0.0.0:8000
   # или
   python -m daphne -b 0.0.0.0 -p 8000 printer_inventory.asgi:application
   ```

2. **База данных с тестовыми данными:**
   - Несколько принтеров в системе
   - Контракты (опционально)
   - Месячные отчеты (опционально)

3. **Keycloak (опционально, для KeycloakAuthUser):**
   ```bash
   docker-compose up keycloak
   ```

### Переменные окружения

Вы можете переопределить учетные данные через environment:

```bash
# Django авторизация
export LOCUST_DJANGO_USER=my_test_user
export LOCUST_DJANGO_PASSWORD=my_password

# Keycloak авторизация
export LOCUST_KEYCLOAK_USER=admin
export LOCUST_KEYCLOAK_PASSWORD=admin123
```

---

## Сценарии тестирования

### DjangoAuthUser

Пользователи, авторизующиеся через стандартную Django форму.

**Распределение задач:**
- 50% - Работа с инвентарем
- 30% - API запросы
- 10% - Контракты
- 10% - Отчеты

**Запуск:**
```bash
locust -f locustfile.py DjangoAuthUser --host=http://localhost:8000
```

### KeycloakAuthUser

Пользователи, авторизующиеся через Keycloak OIDC.

**Требования:**
- Keycloak должен быть запущен
- Пользователь существует в Keycloak realm
- Пользователь добавлен в AllowedUser

**Запуск:**
```bash
locust -f locustfile.py KeycloakAuthUser --host=http://localhost:8000
```

### AnonymousUser

Тестирует только публичные страницы (страницы входа, статические ресурсы).

**Запуск:**
```bash
locust -f locustfile.py AnonymousUser --host=http://localhost:8000
```

### MixedUser

Смешанный сценарий:
- 60% Django auth
- 30% Keycloak auth
- 10% Анонимные

**Запуск:**
```bash
locust -f locustfile.py MixedUser --host=http://localhost:8000
```

---

## Запуск тестов

### Веб-интерфейс

Запустите Locust с веб-интерфейсом:

```bash
locust -f locustfile.py --host=http://localhost:8000
```

Откройте http://localhost:8089 и настройте:
- **Number of users:** Общее количество пользователей
- **Spawn rate:** Скорость добавления пользователей в секунду
- **Host:** URL приложения
- **User class:** Выберите класс пользователей (или оставьте пустым для всех)

### Командная строка (headless)

#### Базовый запуск

```bash
locust -f locustfile.py \
    --host=http://localhost:8000 \
    --users 10 \
    --spawn-rate 2 \
    --run-time 1m \
    --headless
```

#### Расширенные примеры

**Длительный тест с постепенным увеличением нагрузки:**

```bash
locust -f locustfile.py \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 5 \
    --run-time 10m \
    --headless \
    --csv=results/test_$(date +%Y%m%d_%H%M%S)
```

**Тест конкретного класса пользователей:**

```bash
locust -f locustfile.py DjangoAuthUser \
    --host=http://localhost:8000 \
    --users 50 \
    --spawn-rate 5 \
    --run-time 5m \
    --headless
```

**Стресс-тест (высокая нагрузка):**

```bash
locust -f locustfile.py \
    --host=http://localhost:8000 \
    --users 500 \
    --spawn-rate 10 \
    --run-time 3m \
    --headless \
    --csv=results/stress_test
```

### Распределенное тестирование

Для очень высоких нагрузок можно использовать распределенное тестирование.

**Запуск master:**

```bash
locust -f locustfile.py --master --host=http://localhost:8000
```

**Запуск worker (на той же или другой машине):**

```bash
locust -f locustfile.py --worker --master-host=127.0.0.1
```

Запустите несколько workers для увеличения мощности генерации нагрузки.

---

## Результаты и метрики

### Метрики в реальном времени

При использовании веб-интерфейса вы увидите:

- **RPS (Requests Per Second):** Количество запросов в секунду
- **Response time (ms):**
  - Median: Медианное время ответа
  - 95th percentile: 95% запросов быстрее этого времени
- **Failures:** Процент неудачных запросов
- **Active users:** Количество активных виртуальных пользователей

### Экспорт результатов

**CSV файлы:**

```bash
locust -f locustfile.py \
    --host=http://localhost:8000 \
    --headless \
    --csv=results/my_test
```

Создаст файлы:
- `results/my_test_stats.csv` - Статистика по запросам
- `results/my_test_stats_history.csv` - История метрик
- `results/my_test_failures.csv` - История ошибок

**HTML отчет:**

```bash
locust -f locustfile.py \
    --host=http://localhost:8000 \
    --headless \
    --html=results/report.html
```

### Логи

Логи Locust пишутся в stdout. Для сохранения в файл:

```bash
locust -f locustfile.py --host=http://localhost:8000 --headless 2>&1 | tee locust.log
```

---

## Устранение неполадок

### Проблема: Login failed

**Решение:**
1. Убедитесь, что тестовый пользователь создан
2. Проверьте, что пользователь в AllowedUser whitelist
3. Проверьте credentials в environment или в коде

### Проблема: Connection refused

**Решение:**
1. Убедитесь, что приложение запущено: `python manage.py runserver 0.0.0.0:8000`
2. Проверьте правильность URL в `--host`
3. Проверьте firewall

### Проблема: CSRF verification failed

**Решение:**
1. Проверьте, что в `settings.py` установлен `CSRF_TRUSTED_ORIGINS`
2. Убедитесь, что домен в `--host` совпадает с доменом в браузере

### Проблема: Keycloak login failed

**Решение:**
1. Убедитесь, что Keycloak запущен: `docker-compose up keycloak`
2. Проверьте credentials пользователя в Keycloak
3. Убедитесь, что пользователь в AllowedUser whitelist
4. Проверьте логи: `logs/keycloak_auth.log`

### Проблема: Высокий процент ошибок

**Решение:**
1. Уменьшите количество пользователей (`--users`)
2. Уменьшите скорость spawn (`--spawn-rate`)
3. Проверьте логи приложения: `logs/django.log`
4. Увеличьте ресурсы сервера (CPU, RAM)
5. Проверьте, что база данных справляется с нагрузкой

### Проблема: Медленные запросы

Локаст автоматически логирует запросы медленнее 2 секунд.

**Решение:**
1. Проверьте логи: `logs/django.log`
2. Используйте Django Debug Toolbar для анализа запросов
3. Оптимизируйте запросы к БД (добавьте индексы, используйте select_related)
4. Включите кэширование в Redis

---

## Дополнительные возможности

### Кастомные сценарии

Вы можете создать свои собственные TaskSet в `tests/locust/tasks/`.

Пример:

```python
# tests/locust/tasks/custom_tasks.py
from locust import TaskSet, task

class CustomTaskSet(TaskSet):
    @task
    def my_custom_task(self):
        self.client.get("/my-endpoint/")
```

Затем импортируйте и используйте в `locustfile.py`.

### Мониторинг системных ресурсов

Во время тестов следите за:
- CPU и RAM сервера
- Нагрузка на PostgreSQL
- Нагрузка на Redis
- Количество активных connections

Используйте:
```bash
htop
docker stats
```

---

## Рекомендации

### Для разработки

- Начинайте с малого: 5-10 пользователей
- Используйте короткие тесты: 1-2 минуты
- Используйте веб-интерфейс для анализа

### Для staging

- Средняя нагрузка: 50-100 пользователей
- Длительность: 5-10 минут
- Сохраняйте результаты в CSV/HTML

### Для production-подобных тестов

- Высокая нагрузка: 200-500 пользователей
- Длительность: 10-30 минут
- Используйте распределенное тестирование
- Обязательно экспортируйте результаты

### Важно

⚠️ **Не запускайте нагрузочные тесты на production сервере!**

⚠️ **Тест опроса принтеров** (`run_printer_poll`) выполняет реальный SNMP/Web опрос. Используйте с осторожностью при высоких нагрузках!

⚠️ **Экспорт данных** может быть тяжелой операцией. Следите за использованием памяти.

---

## Полезные ссылки

- [Документация Locust](https://docs.locust.io/)
- [Примеры сценариев](https://github.com/locustio/locust/tree/master/examples)
- [Best Practices](https://docs.locust.io/en/stable/writing-a-locustfile.html)

---

**Автор:** AI Assistant
**Дата создания:** 2025-11-23
**Версия:** 1.0
