#!/bin/bash
# Быстрый скрипт для создания offline bundle
# Использование: ./create-npm-bundle.sh

set -e

echo "📦 Создание npm offline bundle..."
echo ""

# Проверяем, что node_modules существует
if [ ! -d "node_modules" ]; then
    echo "⚠️  node_modules не найден. Запускаю npm install..."
    npm install
fi

# Создаём архив
echo "🗜️  Создание архива..."
tar -czf npm-dependencies.tar.gz node_modules package.json package-lock.json

# Показываем размер
SIZE=$(du -h npm-dependencies.tar.gz | cut -f1)
echo ""
echo "✅ Готово!"
echo ""
echo "📄 Файл: npm-dependencies.tar.gz"
echo "📊 Размер: $SIZE"
echo ""
echo "📋 Инструкция по установке на сервере:"
echo ""
echo "  1. Скопируйте npm-dependencies.tar.gz на сервер"
echo "  2. Распакуйте:"
echo "     tar -xzf npm-dependencies.tar.gz"
echo "  3. Проверьте:"
echo "     npm run build"
echo ""
echo "📖 Подробная документация: docs/QUICK_START_OFFLINE.md"
