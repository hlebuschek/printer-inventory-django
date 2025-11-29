# Offline установка npm зависимостей

Если на production сервере нет доступа к интернету, используйте один из следующих способов.

---

## Способ 1: Простое копирование node_modules (рекомендуется)

### На машине с интернетом:

```bash
# 1. Установите зависимости
npm install

# 2. Создайте архив
tar -czf npm-dependencies.tar.gz node_modules package.json package-lock.json

# 3. Перенесите npm-dependencies.tar.gz на сервер
```

### На сервере без интернета:

```bash
# 1. Распакуйте архив в корень проекта
cd /var/www/printer-inventory
tar -xzf npm-dependencies.tar.gz

# 2. Проверьте установку
npm run build
```

**Плюсы:** Самый простой способ
**Минусы:** Большой размер архива (~50-100 MB)

---

## Способ 2: Использование npm cache (меньший размер)

### На машине с интернетом:

```bash
# 1. Очистите и заполните cache
npm cache clean --force
npm install
npm cache verify

# 2. Найдите директорию cache
NPM_CACHE=$(npm config get cache)
echo $NPM_CACHE  # Обычно ~/.npm

# 3. Создайте архив
tar -czf npm-cache.tar.gz -C ~ .npm package.json package-lock.json
```

### На сервере без интернета:

```bash
# 1. Распакуйте cache в home директорию
cd ~
tar -xzf npm-cache.tar.gz

# 2. Скопируйте package файлы
cp package.json package-lock.json /var/www/printer-inventory/

# 3. Установите из cache
cd /var/www/printer-inventory
npm ci --prefer-offline --no-audit
```

**Плюсы:** Меньший размер архива
**Минусы:** Требует дополнительные шаги

---

## Способ 3: Использование автоматического скрипта

Проект включает скрипт для автоматической подготовки offline пакетов.

### На машине с интернетом:

```bash
# 1. Запустите скрипт подготовки
chmod +x npm-offline-setup.sh
./npm-offline-setup.sh

# Скрипт создаст:
# - npm-offline-packages.tar.gz (архив со всем необходимым)
# - Инструкции по установке

# 2. Перенесите npm-offline-packages.tar.gz на сервер
```

### На сервере без интернета:

```bash
# 1. Распакуйте архив
tar -xzf npm-offline-packages.tar.gz
cd npm-offline-packages

# 2. Следуйте инструкциям из INSTALL.md
cat INSTALL.md

# 3. Самый простой вариант:
cp -r node_modules ../
cp package.json package-lock.json ../
cd ..
npm run build
```

---

## Способ 4: Использование verdaccio (для множества серверов)

Если у вас много серверов без интернета, можно поднять локальный npm registry.

### На машине в локальной сети с интернетом:

```bash
# 1. Установите verdaccio
npm install -g verdaccio

# 2. Запустите
verdaccio

# По умолчанию запустится на http://localhost:4873
```

### На серверах без интернета (в той же сети):

```bash
# 1. Настройте npm на использование локального registry
npm config set registry http://<verdaccio-server-ip>:4873/

# 2. Установите зависимости как обычно
npm install

# 3. После установки верните обратно (опционально)
npm config set registry https://registry.npmjs.org/
```

**Плюсы:** Отлично для множества серверов
**Минусы:** Требует дополнительный сервер

---

## Сравнение размеров

Примерные размеры для текущего проекта (6 зависимостей):

| Метод | Размер архива | Время установки |
|-------|--------------|-----------------|
| node_modules | ~80 MB | ~10 сек (копирование) |
| npm cache | ~30 MB | ~30 сек (npm ci) |
| verdaccio | N/A | ~1 мин (первая установка) |

---

## Рекомендации

1. **Для единичной установки:** Используйте Способ 1 (копирование node_modules)
2. **Для регулярных обновлений:** Используйте Способ 2 (npm cache)
3. **Для множества серверов:** Используйте Способ 4 (verdaccio)

---

## Проверка успешной установки

После установки любым способом проверьте:

```bash
# 1. Проверьте, что все пакеты установлены
npm list

# 2. Проверьте сборку
npm run build

# Должно вывести:
# ✓ built in X.XXs
# static/dist/css/main.*.css
# static/dist/js/main.*.js
```

---

## Устранение проблем

### Ошибка: "ENOENT: no such file or directory"

```bash
# Убедитесь, что package.json и package-lock.json скопированы
ls -la package.json package-lock.json
```

### Ошибка: "npm ERR! code ENOTCACHED"

```bash
# Cache не содержит нужных пакетов, используйте Способ 1
```

### Разные версии Node.js

```bash
# На машине с интернетом проверьте версию
node -v

# На сервере должна быть та же мажорная версия (18.x)
# Если версии разные, установите nvm:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18
```

---

## Автоматизация с помощью Makefile

Можно добавить в Makefile:

```makefile
.PHONY: npm-offline-prepare npm-offline-install

npm-offline-prepare:
	@echo "Подготовка offline пакетов..."
	npm install
	tar -czf npm-dependencies.tar.gz node_modules package.json package-lock.json
	@echo "Готово! Файл: npm-dependencies.tar.gz"

npm-offline-install:
	@echo "Установка из offline архива..."
	tar -xzf npm-dependencies.tar.gz
	@echo "Проверка..."
	npm run build
```

Использование:

```bash
# На машине с интернетом:
make npm-offline-prepare

# На сервере:
make npm-offline-install
```
