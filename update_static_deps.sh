#!/bin/bash

# Скрипт для обновления всех статических зависимостей
# Запуск: bash update_static_deps.sh

set -e  # Прерывать при ошибках

echo "🔄 Обновление статических зависимостей..."

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Создаём директории
echo -e "${YELLOW}📁 Создание структуры директорий...${NC}"
mkdir -p static/js/vendor
mkdir -p static/css/vendor
mkdir -p static/fonts/bootstrap-icons

# Функция для скачивания с проверкой
download_file() {
    local url=$1
    local output=$2
    local description=$3

    echo -e "${YELLOW}⬇️  Скачивание: ${description}${NC}"

    if curl -L --fail --silent --show-error "$url" -o "$output"; then
        echo -e "${GREEN}✅ ${description} - OK${NC}"
        return 0
    else
        echo -e "${RED}❌ Ошибка при скачивании: ${description}${NC}"
        return 1
    fi
}

# ========== Alpine.js ==========
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📦 Alpine.js${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

ALPINE_VERSION="3.13.3"
download_file \
    "https://cdn.jsdelivr.net/npm/alpinejs@${ALPINE_VERSION}/dist/cdn.min.js" \
    "static/js/vendor/alpine.min.js" \
    "Alpine.js ${ALPINE_VERSION} (minified)"

download_file \
    "https://cdn.jsdelivr.net/npm/alpinejs@${ALPINE_VERSION}/dist/cdn.js" \
    "static/js/vendor/alpine.js" \
    "Alpine.js ${ALPINE_VERSION} (full)"

# Плагины Alpine.js (опционально)
read -p "Скачать плагины Alpine.js? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    download_file \
        "https://cdn.jsdelivr.net/npm/@alpinejs/persist@${ALPINE_VERSION}/dist/cdn.min.js" \
        "static/js/vendor/alpine-persist.min.js" \
        "Alpine Persist plugin"

    download_file \
        "https://cdn.jsdelivr.net/npm/@alpinejs/focus@${ALPINE_VERSION}/dist/cdn.min.js" \
        "static/js/vendor/alpine-focus.min.js" \
        "Alpine Focus plugin"

    download_file \
        "https://cdn.jsdelivr.net/npm/@alpinejs/collapse@${ALPINE_VERSION}/dist/cdn.min.js" \
        "static/js/vendor/alpine-collapse.min.js" \
        "Alpine Collapse plugin"
fi

# ========== Bootstrap ==========
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📦 Bootstrap${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

BOOTSTRAP_VERSION="5.3.0"
download_file \
    "https://cdn.jsdelivr.net/npm/bootstrap@${BOOTSTRAP_VERSION}/dist/css/bootstrap.min.css" \
    "static/css/vendor/bootstrap.min.css" \
    "Bootstrap CSS ${BOOTSTRAP_VERSION}"

download_file \
    "https://cdn.jsdelivr.net/npm/bootstrap@${BOOTSTRAP_VERSION}/dist/css/bootstrap.min.css.map" \
    "static/css/vendor/bootstrap.min.css.map" \
    "Bootstrap CSS Source Map"

download_file \
    "https://cdn.jsdelivr.net/npm/bootstrap@${BOOTSTRAP_VERSION}/dist/js/bootstrap.bundle.min.js" \
    "static/js/vendor/bootstrap.bundle.min.js" \
    "Bootstrap JS ${BOOTSTRAP_VERSION}"

download_file \
    "https://cdn.jsdelivr.net/npm/bootstrap@${BOOTSTRAP_VERSION}/dist/js/bootstrap.bundle.min.js.map" \
    "static/js/vendor/bootstrap.bundle.min.js.map" \
    "Bootstrap JS Source Map"

# ========== Bootstrap Icons ==========
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📦 Bootstrap Icons${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

BOOTSTRAP_ICONS_VERSION="1.10.5"
download_file \
    "https://cdn.jsdelivr.net/npm/bootstrap-icons@${BOOTSTRAP_ICONS_VERSION}/font/bootstrap-icons.css" \
    "static/css/vendor/bootstrap-icons.css" \
    "Bootstrap Icons CSS ${BOOTSTRAP_ICONS_VERSION}"

download_file \
    "https://cdn.jsdelivr.net/npm/bootstrap-icons@${BOOTSTRAP_ICONS_VERSION}/font/fonts/bootstrap-icons.woff" \
    "static/fonts/bootstrap-icons/bootstrap-icons.woff" \
    "Bootstrap Icons Font (WOFF)"

download_file \
    "https://cdn.jsdelivr.net/npm/bootstrap-icons@${BOOTSTRAP_ICONS_VERSION}/font/fonts/bootstrap-icons.woff2" \
    "static/fonts/bootstrap-icons/bootstrap-icons.woff2" \
    "Bootstrap Icons Font (WOFF2)"

# Исправляем пути в CSS
echo -e "${YELLOW}🔧 Исправление путей в bootstrap-icons.css...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' 's|url("./fonts/|url("../../fonts/bootstrap-icons/|g' static/css/vendor/bootstrap-icons.css
else
    # Linux
    sed -i 's|url("./fonts/|url("../../fonts/bootstrap-icons/|g' static/css/vendor/bootstrap-icons.css
fi
echo -e "${GREEN}✅ Пути исправлены${NC}"

# ========== Chart.js ==========
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}📦 Chart.js${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

CHARTJS_VERSION="4.4.0"
download_file \
    "https://cdn.jsdelivr.net/npm/chart.js@${CHARTJS_VERSION}/dist/chart.umd.min.js" \
    "static/js/vendor/chart.min.js" \
    "Chart.js ${CHARTJS_VERSION}"

# ========== Итоги ==========
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✨ Готово!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Показываем размеры
echo -e "\n${YELLOW}📊 Размеры файлов:${NC}"
du -sh static/js/vendor/*
du -sh static/css/vendor/*
du -sh static/fonts/bootstrap-icons/*

echo -e "\n${GREEN}🎉 Все зависимости успешно скачаны!${NC}"
echo -e "${YELLOW}💡 Не забудьте запустить:${NC}"
echo -e "   ${YELLOW}python manage.py collectstatic${NC}"