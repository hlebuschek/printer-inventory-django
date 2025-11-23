# Нагрузочное тестирование (Load Testing)

Этот проект включает комплексную систему нагрузочного тестирования на базе [Locust](https://locust.io/).

## Быстрый старт

### 1. Установка

```bash
pip install -r requirements-dev.txt
```

### 2. Создание тестовых пользователей

```bash
python tests/locust/setup_test_users.py
```

### 3. Запуск тестов

```bash
./run_locust.sh web
```

Откройте http://localhost:8089 в браузере.

## Возможности

✅ **Авторизация через Django и Keycloak**
- Полная поддержка OIDC flow для Keycloak
- Стандартная Django форма авторизации
- Проверка whitelist (AllowedUser)

✅ **Реалистичные сценарии**
- Работа с инвентарем принтеров
- API запросы
- Управление контрактами
- Месячные отчеты

✅ **Гибкие конфигурации**
- Предустановленные режимы (quick, medium, stress)
- Конфигурация через файл или командную строку
- Поддержка распределенного тестирования

## Основные команды

### Веб-интерфейс
```bash
./run_locust.sh web
```

### Быстрый тест (1 минута, 10 пользователей)
```bash
./run_locust.sh quick
```

### Средний тест (5 минут, 50 пользователей)
```bash
./run_locust.sh medium
```

### Стресс-тест (10 минут, 200 пользователей)
```bash
./run_locust.sh stress
```

### Тест Django авторизации
```bash
./run_locust.sh django
```

### Тест Keycloak авторизации
```bash
# Сначала запустите Keycloak
docker-compose up keycloak

# Затем запустите тест
./run_locust.sh keycloak
```

## Классы пользователей

### DjangoAuthUser
Пользователи, авторизующиеся через Django форму.
- Username: `locust_test`
- Password: `locust_password_123`

### KeycloakAuthUser
Пользователи, авторизующиеся через Keycloak OIDC.
- Username: `user`
- Password: `12345678`

### AnonymousUser
Тестирование публичных страниц (страницы входа, статические ресурсы).

### MixedUser
Смешанный сценарий (60% Django, 30% Keycloak, 10% анонимные).

## Структура проекта

```
printer-inventory-django/
├── locustfile.py                    # Главный файл Locust
├── run_locust.sh                    # Скрипт для запуска
├── requirements-dev.txt             # Dev зависимости
└── tests/locust/
    ├── README.md                    # Полная документация
    ├── QUICKSTART.md                # Быстрый старт
    ├── locust.conf                  # Конфигурация
    ├── setup_test_users.py          # Скрипт создания пользователей
    ├── results/                     # Результаты тестов (CSV, HTML)
    ├── logs/                        # Логи
    └── tasks/                       # Модули задач
        ├── auth_tasks.py            # Авторизация
        ├── inventory_tasks.py       # Инвентарь
        ├── api_tasks.py             # API
        ├── contract_tasks.py        # Контракты
        └── report_tasks.py          # Отчеты
```

## Настройка через переменные окружения

```bash
# Django авторизация
export LOCUST_DJANGO_USER=my_user
export LOCUST_DJANGO_PASSWORD=my_password

# Keycloak авторизация
export LOCUST_KEYCLOAK_USER=admin
export LOCUST_KEYCLOAK_PASSWORD=admin123

# URL приложения
export LOCUST_HOST=http://192.168.1.100:8000
```

## Результаты

### Веб-интерфейс
- **Statistics:** Общая статистика по запросам
- **Charts:** Графики RPS, времени ответа, количества пользователей
- **Failures:** Список ошибок
- **Download Data:** Экспорт в CSV

### Файлы результатов
Headless режим сохраняет результаты в `tests/locust/results/`:
- `*_stats.csv` - Статистика запросов
- `*_stats_history.csv` - История метрик
- `*_failures.csv` - История ошибок
- `*.html` - HTML отчет

## Документация

- **Полная документация:** [tests/locust/README.md](tests/locust/README.md)
- **Быстрый старт:** [tests/locust/QUICKSTART.md](tests/locust/QUICKSTART.md)
- **Документация Locust:** https://docs.locust.io/

## Рекомендации

### ⚠️ Важно

- **Не запускайте на production!** Используйте только staging/dev окружения
- **Опрос принтеров** запускает реальные SNMP/Web запросы - используйте осторожно
- **Экспорт данных** может быть ресурсоемким при высоких нагрузках
- Следите за использованием ресурсов сервера (CPU, RAM, DB connections)

### Для разработки
- Начинайте с малого: 5-10 пользователей
- Используйте короткие тесты: 1-2 минуты
- Используйте веб-интерфейс для анализа

### Для staging
- Средняя нагрузка: 50-100 пользователей
- Длительность: 5-10 минут
- Сохраняйте результаты в CSV/HTML

### Для оценки максимальной нагрузки
- Постепенно увеличивайте пользователей
- Используйте распределенное тестирование
- Мониторьте все компоненты системы (Django, PostgreSQL, Redis, Celery)

## Устранение проблем

### Login failed
```bash
# Проверьте пользователей
python tests/locust/setup_test_users.py --show

# Пересоздайте пользователей
python tests/locust/setup_test_users.py
```

### Connection refused
```bash
# Убедитесь, что приложение запущено
python manage.py runserver 0.0.0.0:8000
```

### Keycloak login failed
```bash
# Проверьте Keycloak
docker-compose ps keycloak
docker-compose logs keycloak

# Проверьте логи авторизации
tail -f logs/keycloak_auth.log
```

## Примеры использования

### Тест производительности API
```bash
locust -f locustfile.py APITaskSet \
    --host=http://localhost:8000 \
    --users=100 \
    --spawn-rate=10 \
    --run-time=5m \
    --headless
```

### Распределенный тест
```bash
# Master
locust -f locustfile.py --master --host=http://localhost:8000

# Workers (запустите несколько)
locust -f locustfile.py --worker --master-host=127.0.0.1
```

### Тест с кастомными параметрами
```bash
./run_locust.sh web --users=200 --spawn-rate=10
```

---

**Версия:** 1.0
**Дата:** 2025-11-23
**Автор:** AI Assistant
