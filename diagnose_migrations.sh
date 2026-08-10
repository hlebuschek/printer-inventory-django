#!/bin/bash
# Диагностика состояния миграций на сервере. Только чтение: ничего не мигрирует,
# не пишет в БД и не создаёт файлы миграций.
#
#   ./diagnose_migrations.sh              # /var/www/printer-inventory
#   PROJECT_DIR=/path/to/proj ./diagnose_migrations.sh

PROJECT_DIR="${PROJECT_DIR:-/var/www/printer-inventory}"
VENV="${VENV:-$PROJECT_DIR/.venv}"

echo "========================================================================"
echo "🔍 ДИАГНОСТИКА МИГРАЦИЙ"
echo "========================================================================"
echo "   хост:    $(hostname)"
echo "   дата:    $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "   проект:  $PROJECT_DIR"
echo ""

if [ ! -f "$PROJECT_DIR/manage.py" ]; then
    echo "❌ Не найден $PROJECT_DIR/manage.py — задай PROJECT_DIR."
    exit 1
fi
cd "$PROJECT_DIR" || exit 1

if [ -f "$VENV/bin/activate" ]; then
    # shellcheck disable=SC1091
    . "$VENV/bin/activate"
    echo "   venv:    $VENV"
else
    echo "⚠️  Не найден $VENV/bin/activate — работаю системным python."
fi
echo "   python:  $(python -V 2>&1)"
echo "   django:  $(python -c 'import django; print(django.get_version())' 2>/dev/null || echo '?')"
echo ""

PY_OUT=$(python manage.py shell 2>&1 <<'PYEOF'
import sys
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.loader import MigrationLoader

base = str(settings.BASE_DIR)
local = sorted(
    a.label
    for a in apps.get_app_configs()
    if str(a.path).startswith(base) and "site-packages" not in str(a.path)
)

loader = MigrationLoader(connection, ignore_no_migrations=True)
disk, applied = set(loader.disk_migrations), set(loader.applied_migrations)

print("@@SECTION:conflicts")
conflicts = loader.detect_conflicts()
if conflicts:
    for app, names in sorted(conflicts.items()):
        print(f"FAIL {app}: {len(names)} листьев -> {', '.join(sorted(names))}")
else:
    print("OK единственный лист в каждом приложении")

print("@@SECTION:history")
try:
    loader.check_consistent_history(connection)
    print("OK порядок применения непротиворечив")
except Exception as exc:
    print(f"FAIL {exc}")

print("@@SECTION:ghosts")
ghosts = sorted(applied - disk)
mine = [g for g in ghosts if g[0] in local]
other = [g for g in ghosts if g[0] not in local]
if mine:
    for app, name in mine:
        print(f"WARN {app}.{name} — есть в django_migrations, файла нет")
    print("     (след удалённой/переименованной миграции; опасно только если п.1 и п.2 тоже ругаются)")
else:
    print("OK призраков в приложениях проекта нет")
for app, name in other:
    print(f"note {app}.{name} — чужое/удалённое приложение, обычно безвредно")

print("@@SECTION:unapplied")
un = sorted(m for m in disk - applied if m[0] in local)
if un:
    for app, name in un:
        print(f"WARN {app}.{name} — файл есть, не применена")
else:
    print("OK все миграции проекта применены")

print("@@SECTION:manifest")
for app in local:
    names = sorted(n for a, n in disk if a == app)
    print(f"{app}: {len(names)}" + (f" | последняя: {names[-1]}" if names else " | пусто"))
PYEOF
)

section() { printf '%s\n' "$PY_OUT" | awk -v s="@@SECTION:$1" '$0==s{f=1;next} /^@@SECTION:/{f=0} f'; }

if ! printf '%s\n' "$PY_OUT" | grep -q '@@SECTION:conflicts'; then
    echo "❌ Не удалось опросить Django. Вывод:"
    printf '%s\n' "$PY_OUT"
    exit 1
fi

echo "1️⃣ Конфликты графа (несколько листьев в приложении):"
section conflicts | sed 's/^/   /'
echo ""

echo "2️⃣ Непротиворечивость истории применения:"
section history | sed 's/^/   /'
echo ""

echo "3️⃣ Призраки: запись в django_migrations без файла на диске:"
section ghosts | sed 's/^/   /'
echo ""

echo "4️⃣ Неприменённые миграции:"
section unapplied | sed 's/^/   /'
echo ""

echo "5️⃣ Дрейф моделей относительно миграций:"
DRIFT=$(python manage.py makemigrations --check --dry-run 2>&1)
if [ $? -eq 0 ]; then
    echo "   OK модели совпадают с миграциями"
else
    echo "   WARN есть незакоммиченные изменения моделей либо граф сломан:"
    printf '%s\n' "$DRIFT" | sed 's/^/     /'
fi
echo ""

echo "6️⃣ Сводка по приложениям проекта:"
section manifest | sed 's/^/   /'
echo ""

echo "7️⃣ Манифест файлов миграций (md5 — для сверки с репозиторием):"
if command -v md5sum >/dev/null 2>&1; then md5of() { md5sum "$1" | cut -c1-32; }
else md5of() { md5 -q "$1"; }; fi
find . -path ./.venv -prune -o -path '*/migrations/0*.py' -print 2>/dev/null \
    | sed 's|^\./||' | sort | while read -r f; do
        printf '   %s  %s\n' "$(md5of "$f")" "$f"
    done
echo ""

echo "8️⃣ Осиротевшие .pyc без исходника (мусор от копирующего деплоя):"
ORPHANS=$(find . -path ./.venv -prune -o -name '__pycache__' -print 2>/dev/null | while read -r c; do
    for f in "$c"/*.pyc; do
        [ -e "$f" ] || continue
        src="$(dirname "$c")/$(basename "$f" | cut -d. -f1).py"
        [ -e "$src" ] || echo "$f"
    done
done)
if [ -z "$ORPHANS" ]; then
    echo "   OK не найдено"
else
    printf '%s\n' "$ORPHANS" | sed 's/^/   /'
    echo "   ─────"
    echo "   всего: $(printf '%s\n' "$ORPHANS" | wc -l)"
fi
echo ""

echo "========================================================================"
echo "Готово. Ни одна команда выше не изменяла БД и не создавала миграций."
echo "========================================================================"
