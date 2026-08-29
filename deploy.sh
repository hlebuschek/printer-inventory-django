#!/usr/bin/env bash
# Деплой релиза на прод-сервер.
#
# Использование:
#   1. Скопировать проект на сервер (scp/rsync) в любую папку
#   2. Свежие wheels (если менялся requirements.txt) — в pip_packages РЯДОМ с папкой проекта
#   3. sudo bash /путь/к/проекту/deploy.sh
#
# Скрипт сам: бекапит текущую установку, раскатывает файлы, ставит pip-пакеты
# офлайн, собирает фронт, применяет миграции, чинит права и перезапускает сервисы.

set -euo pipefail

# ─── Настройки ───────────────────────────────────────────────────────────
SRC_DIR="${SRC_DIR:-$(cd "$(dirname "$0")" && pwd)}"   # откуда катим (папка со скриптом)
APP_DIR="${APP_DIR:-/var/www/printer-inventory}"        # куда катим
WHEELS_DIR="${WHEELS_DIR:-$(dirname "$SRC_DIR")/pip_packages}" # офлайн pip-пакеты (рядом с папкой проекта)
BACKUP_ROOT="${BACKUP_ROOT:-/var/www/backups}"          # куда складывать бекапы
SERVICES=(daphne.service celery-worker.service celery-beat.service)
APP_USER="www-data"

# Python из venv проекта (source activate не нужен — вызываем бинарь напрямую).
# Можно переопределить: PY=/путь/к/venv/bin/python sudo -E bash deploy.sh
if [ -z "${PY:-}" ]; then
    if [ -x "$APP_DIR/.venv/bin/python" ]; then
        PY="$APP_DIR/.venv/bin/python"
    elif [ -x "$APP_DIR/venv/bin/python" ]; then
        PY="$APP_DIR/venv/bin/python"
    else
        die "venv не найден в $APP_DIR (.venv/venv) — укажи PY=/путь/к/python"
    fi
fi

log() { echo -e "\n\033[1;34m==> $*\033[0m"; }
die() { echo -e "\033[1;31mОШИБКА: $*\033[0m" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "запускать через sudo"
[ -f "$SRC_DIR/manage.py" ] || die "в $SRC_DIR нет manage.py — не похоже на проект"
[ -d "$APP_DIR" ] || die "нет каталога $APP_DIR"

STAMP="$(date +%Y-%m-%d_%H%M)"

# ─── 1. Бекап текущей установки ─────────────────────────────────────────
BACKUP_DIR="$BACKUP_ROOT/printer-inventory_$STAMP"
log "Бекап $APP_DIR -> $BACKUP_DIR"
mkdir -p "$BACKUP_ROOT"
# --exclude: node_modules и логи в бекапе не нужны, media бекапится
# код 24 (vanished files) не считаем ошибкой: GLPI Agent пишет/удаляет
# временные XML в inventory_output во время бекапа
rsync -a --exclude node_modules --exclude logs "$APP_DIR/" "$BACKUP_DIR/" \
    || { rc=$?; [ "$rc" -eq 24 ] || exit "$rc"; }

# ─── 2. Бекап БД (если на этой же машине есть pg_dump) ──────────────────
if command -v pg_dump >/dev/null 2>&1 && [ -f "$APP_DIR/.env" ]; then
    DB_NAME=$(grep -E '^DB_NAME=' "$APP_DIR/.env" | cut -d= -f2- || true)
    if [ -n "${DB_NAME:-}" ]; then
        log "Дамп БД $DB_NAME -> $BACKUP_DIR/db_$STAMP.sql.gz"
        sudo -u postgres pg_dump "$DB_NAME" | gzip > "$BACKUP_DIR/db_$STAMP.sql.gz" \
            || echo "ВНИМАНИЕ: дамп БД не удался, продолжаем (бекап файлов есть)"
    fi
fi

# ─── 3. Раскатка файлов ─────────────────────────────────────────────────
log "rsync $SRC_DIR -> $APP_DIR"
# Если релиз без собранного фронта — не даём --delete снести прошлый dist
RSYNC_EXTRA=()
if [ ! -f "$SRC_DIR/static/dist/.vite/manifest.json" ]; then
    RSYNC_EXTRA+=(--exclude "static/dist/")
fi
# .env и media НЕ перезаписываем: на проме свои
rsync -a --delete \
    "${RSYNC_EXTRA[@]}" \
    --exclude ".env" \
    --exclude "media/" \
    --exclude "logs/" \
    --exclude ".git/" \
    --exclude "__pycache__/" \
    --exclude "*.pyc" \
    --exclude "venv/" \
    --exclude ".venv/" \
    --exclude "node_modules/" \
    --exclude "edgedriver_*/" \
    --exclude "inventory_output/" \
    "$SRC_DIR/" "$APP_DIR/"

cd "$APP_DIR"

# ─── 4. Pip-пакеты (офлайн) ─────────────────────────────────────────────
if [ -d "$WHEELS_DIR" ]; then
    log "pip install из $WHEELS_DIR ($PY)"
    # Сначала обновляем сам pip (старый может не понять свежие wheels)
    "$PY" -m pip install --no-index --find-links="$WHEELS_DIR" --upgrade pip || true
    "$PY" -m pip install --no-index --find-links="$WHEELS_DIR" -r requirements.txt
else
    echo "ВНИМАНИЕ: $WHEELS_DIR не найден — pip-пакеты не обновлялись"
fi

# ─── 5. Фронтенд и статика (строго последовательно!) ────────────────────
# Сервер офлайн: если фронт собран локально (dist приехал с rsync) — npm не нужен
if [ -f "$SRC_DIR/static/dist/.vite/manifest.json" ]; then
    log "static/dist приехал с релизом — npm build не нужен"
elif [ -d "$APP_DIR/node_modules" ]; then
    log "npm run build"
    npm run build
elif [ -f "$APP_DIR/static/dist/.vite/manifest.json" ]; then
    echo -e "\033[1;33mВНИМАНИЕ: в релизе нет static/dist — остаётся фронт от ПРОШЛОГО релиза."
    echo -e "Если фронтенд менялся: npm run build локально и перекатить dist.\033[0m"
else
    die "нет node_modules и нет static/dist ни в релизе, ни на проме — собери фронт локально (npm install && npm run build) и перекати"
fi
log "collectstatic"
"$PY" manage.py collectstatic --noinput

# ─── 6. Миграции (makemigrations на проме НЕ делаем) ────────────────────
log "migrate"
"$PY" manage.py migrate --noinput

# ─── 7. Права ────────────────────────────────────────────────────────────
log "chown $APP_USER"
mkdir -p "$APP_DIR/media" "$APP_DIR/logs"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ─── 8. Перезапуск сервисов ──────────────────────────────────────────────
log "Перезапуск: ${SERVICES[*]}"
systemctl restart "${SERVICES[@]}"
sleep 3
FAILED=0
for s in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$s"; then
        echo "  ✓ $s"
    else
        echo "  ✗ $s НЕ ЗАПУСТИЛСЯ — journalctl -u $s -n 50"
        FAILED=1
    fi
done

# ─── Итог ────────────────────────────────────────────────────────────────
if [ "$FAILED" -eq 0 ]; then
    log "Деплой завершён. Бекап: $BACKUP_DIR"
else
    die "Сервисы не поднялись. Откат: rsync -a --exclude media $BACKUP_DIR/ $APP_DIR/ && systemctl restart ${SERVICES[*]}"
fi
