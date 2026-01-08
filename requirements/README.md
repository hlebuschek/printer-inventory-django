# Requirements Directory

Эта папка содержит различные файлы зависимостей для разных окружений.

## Файлы

### `daphne-requirements.txt`
Зависимости для ASGI сервера Daphne (WebSocket support).

Установка:
```bash
pip install -r requirements/daphne-requirements.txt
```

### `requirements-dev.txt`
Зависимости для разработки (тестирование, отладка, линтеры).

Установка:
```bash
pip install -r requirements/requirements-dev.txt
```

## Основные зависимости

Основные зависимости проекта находятся в корневом файле:
- `../requirements.txt` - базовые зависимости Django проекта

## Полная установка

```bash
# Основные зависимости
pip install -r requirements.txt

# Для WebSocket поддержки
pip install -r requirements/daphne-requirements.txt

# Для разработки
pip install -r requirements/requirements-dev.txt
```
