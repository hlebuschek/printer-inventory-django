#!/bin/bash
# Скрипт для сборки npm bundle на MacBook для Linux сервера
# Автоматически переключается на Node.js 18 через nvm

set -e

echo "🔧 Сборка npm bundle для Linux сервера (Node.js 18)"
echo ""

# Проверяем, что nvm установлен
if ! command -v nvm &> /dev/null; then
    echo "❌ nvm не установлен!"
    echo ""
    echo "Установите nvm:"
    echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash"
    echo "  source ~/.zshrc  # или ~/.bash_profile"
    echo ""
    echo "Или создайте архив вручную:"
    echo "  npm install"
    echo "  tar -czf npm-dependencies.tar.gz node_modules package.json package-lock.json"
    exit 1
fi

# Загружаем nvm (может потребоваться для скрипта)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Переключаемся на Node 18
echo "📌 Переключение на Node.js 18..."
nvm use 18 || {
  echo "⚠️  Node.js 18 не установлен. Устанавливаю..."
  nvm install 18
  nvm use 18
}

# Проверяем версию
NODE_VERSION=$(node -v)
NPM_VERSION=$(npm -v)
echo "✅ Node.js: $NODE_VERSION"
echo "✅ npm: $NPM_VERSION"
echo ""

# Проверяем, что мы на правильной версии
if [[ ! "$NODE_VERSION" =~ ^v18\. ]]; then
    echo "⚠️  ПРЕДУПРЕЖДЕНИЕ: Версия Node.js не 18.x"
    echo "   Текущая: $NODE_VERSION"
    echo "   Сервер: v18.20.4"
    echo ""
    read -p "Продолжить? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Очищаем старые зависимости
echo "🧹 Очистка старых зависимостей..."
rm -rf node_modules package-lock.json

# Устанавливаем зависимости
echo "📦 Установка зависимостей для Linux..."
npm install

# Проверяем, что установлены правильные платформо-специфичные пакеты
echo ""
echo "🔍 Проверка платформо-специфичных пакетов..."
if [ -d "node_modules/@esbuild/linux-x64" ]; then
    echo "✅ @esbuild/linux-x64 установлен"
else
    echo "❌ @esbuild/linux-x64 НЕ установлен!"
    echo "   Проверьте, что package-lock.json не содержит darwin пакеты"
fi

# Создаём архив
echo ""
echo "🗜️  Создание архива..."
tar -czf npm-dependencies.tar.gz node_modules package.json package-lock.json

SIZE=$(du -h npm-dependencies.tar.gz | cut -f1)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Готово!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📄 Файл: npm-dependencies.tar.gz"
echo "📊 Размер: $SIZE"
echo "🎯 Node.js: $NODE_VERSION"
echo "🖥️  Платформа: Linux x64"
echo ""
echo "📝 Следующие шаги:"
echo ""
echo "1. Скопируйте на сервер:"
echo "   scp npm-dependencies.tar.gz user@server:/var/www/printer-inventory/"
echo ""
echo "2. На сервере распакуйте:"
echo "   ssh server"
echo "   cd /var/www/printer-inventory"
echo "   tar -xzf npm-dependencies.tar.gz"
echo ""
echo "3. Проверьте:"
echo "   npm run build"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
