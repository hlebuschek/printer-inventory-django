# Быстрый старт: Offline установка npm

Для сервера **БЕЗ** интернета.

---

## Вариант 1: Самый простой способ (рекомендуется)

### На машине с интернетом:

```bash
# 1. Клонируйте репозиторий и установите зависимости
cd printer-inventory-django
npm install

# 2. Создайте архив с зависимостями
tar -czf npm-dependencies.tar.gz node_modules package.json package-lock.json

# 3. Перенесите npm-dependencies.tar.gz на сервер
# (через scp, флешку, или другим способом)
```

### На сервере без интернета:

```bash
# 1. Распакуйте архив в директорию проекта
cd /var/www/printer-inventory
tar -xzf npm-dependencies.tar.gz

# 2. Проверьте, что всё работает
npm run build

# Должно вывести:
# vite v5.x.x building for production...
# ✓ built in X.XXs
```

✅ **Готово!** Теперь можно использовать `npm run build` и `npm run dev`

---

## Вариант 2: Использование автоматического скрипта

### На машине с интернетом:

```bash
# 1. Запустите скрипт
./npm-offline-setup.sh

# Скрипт автоматически:
# - Установит все зависимости
# - Создаст npm-offline-packages.tar.gz
# - Подготовит инструкции

# 2. Перенесите npm-offline-packages.tar.gz на сервер
```

### На сервере без интернета:

```bash
# 1. Распакуйте архив
tar -xzf npm-offline-packages.tar.gz
cd npm-offline-packages

# 2. Прочитайте инструкции
cat INSTALL.md

# 3. Установите (самый простой способ)
cp -r node_modules /var/www/printer-inventory/
cp package.json package-lock.json /var/www/printer-inventory/

# 4. Проверьте
cd /var/www/printer-inventory
npm run build
```

---

## Размер файлов

Для текущего проекта (Vue 3 + Vite):

- `npm-dependencies.tar.gz`: ~20-30 MB (сжатый)
- `node_modules/`: ~80-100 MB (распакованный)

---

## Проверка версии Node.js

**ВАЖНО:** На машине с интернетом и на сервере должна быть одинаковая мажорная версия Node.js!

```bash
# Проверьте версию
node -v

# Должно быть: v18.x.x или выше
```

Если версии разные:

```bash
# Установите nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc

# Установите нужную версию
nvm install 18
nvm use 18
nvm alias default 18
```

---

## Что делать после установки?

После успешной offline установки npm:

```bash
# 1. Соберите production версию
npm run build

# 2. Запустите Django collectstatic (если нужно)
python manage.py collectstatic --noinput

# 3. Перезапустите веб-сервер
sudo systemctl restart nginx
sudo systemctl restart daphne  # или gunicorn
```

---

## Если что-то пошло не так

### Ошибка: "vite: not found"

```bash
# Проверьте, что node_modules установлены
ls -la node_modules/.bin/vite

# Если файла нет, распакуйте архив заново
```

### Ошибка: "Cannot find module 'vue'"

```bash
# Зависимости не установлены полностью
# Используйте Вариант 1 (копирование node_modules целиком)
```

### Ошибка: "Permission denied"

```bash
# Настройте права доступа
sudo chown -R $USER:$USER node_modules
chmod +x node_modules/.bin/*
```

---

## Обновление зависимостей в будущем

Когда выйдет новая версия проекта с обновлёнными зависимостями:

```bash
# На машине с интернетом:
git pull
npm install
tar -czf npm-dependencies.tar.gz node_modules package.json package-lock.json

# Перенесите новый архив на сервер и распакуйте
```

---

## Дополнительная документация

Подробная документация: [docs/NPM_OFFLINE_INSTALL.md](NPM_OFFLINE_INSTALL.md)

Включает:
- Способ с npm cache (меньший размер архива)
- Настройку verdaccio для множества серверов
- Устранение проблем
- Сравнение методов
