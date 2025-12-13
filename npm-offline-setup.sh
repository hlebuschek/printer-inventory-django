#!/bin/bash
# Скрипт для подготовки npm зависимостей для offline установки
# Запустите этот скрипт на машине с интернетом

set -e

echo "=== Подготовка npm зависимостей для offline установки ==="

# Создаём директорию для offline пакетов
OFFLINE_DIR="npm-offline-packages"
mkdir -p "$OFFLINE_DIR"

echo ""
echo "Шаг 1: Установка зависимостей и создание package-lock.json..."
npm install

echo ""
echo "Шаг 2: Упаковка всех зависимостей..."

# Создаём список всех зависимостей
npm list --prod --json > "$OFFLINE_DIR/dependencies.json"
npm list --dev --json > "$OFFLINE_DIR/dev-dependencies.json"

# Копируем package.json и package-lock.json
cp package.json "$OFFLINE_DIR/"
cp package-lock.json "$OFFLINE_DIR/"

# Упаковываем npm cache
echo ""
echo "Шаг 3: Копирование npm cache..."
NPM_CACHE_DIR=$(npm config get cache)
cp -r "$NPM_CACHE_DIR" "$OFFLINE_DIR/npm-cache"

# Копируем node_modules (самый простой способ)
echo ""
echo "Шаг 4: Копирование node_modules..."
cp -r node_modules "$OFFLINE_DIR/"

# Создаём инструкцию по установке
cat > "$OFFLINE_DIR/INSTALL.md" << 'EOF'
# Offline установка npm зависимостей

## Способ 1: Копирование node_modules (самый простой)

```bash
# На сервере без интернета:
cp -r node_modules /path/to/printer-inventory-django/
cp package.json /path/to/printer-inventory-django/
cp package-lock.json /path/to/printer-inventory-django/
```

## Способ 2: Использование npm cache

```bash
# На сервере без интернета:
# 1. Скопируйте npm-cache в локальную директорию
mkdir -p ~/.npm
cp -r npm-cache/* ~/.npm/

# 2. Скопируйте package.json и package-lock.json
cp package.json /path/to/printer-inventory-django/
cp package-lock.json /path/to/printer-inventory-django/

# 3. Установите из кэша
cd /path/to/printer-inventory-django/
npm ci --prefer-offline --no-audit
```

## Способ 3: Установка из локальной директории

```bash
# На сервере без интернета:
cd /path/to/printer-inventory-django/
npm install --offline --cache /path/to/npm-offline-packages/npm-cache
```

## Проверка установки

```bash
npm list
npm run build
```
EOF

# Создаём архив
echo ""
echo "Шаг 5: Создание архива..."
tar -czf npm-offline-packages.tar.gz "$OFFLINE_DIR"

echo ""
echo "=== Готово! ==="
echo ""
echo "Файл npm-offline-packages.tar.gz содержит все необходимые зависимости."
echo "Размер архива:"
du -h npm-offline-packages.tar.gz
echo ""
echo "Инструкция по установке находится в: $OFFLINE_DIR/INSTALL.md"
echo ""
echo "Перенесите файл npm-offline-packages.tar.gz на сервер и распакуйте:"
echo "  tar -xzf npm-offline-packages.tar.gz"
echo "  cd npm-offline-packages"
echo "  cat INSTALL.md"
