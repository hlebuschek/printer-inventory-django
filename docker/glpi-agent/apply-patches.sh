#!/bin/sh
# Накладывает модифицированные MibSupport-модули (раздельные счётчики A3/A4)
# поверх установленного glpi-agent.
#
# Guard: перед заменой сверяем sha256 установленных апстрим-файлов со списком
# известных чистых версий (pristine.sha256, файлы не менялись апстримом с 1.16).
# Если апстрим изменил какой-то из этих файлов — сборка падает: правки нужно
# пересмотреть вручную, а не молча затирать новый функционал.
set -eu

SRC_DIR="$(dirname "$0")/mibsupport"
DST_DIR="/usr/share/glpi-agent/lib/GLPI/Agent/SNMP/MibSupport"
PRISTINE="$(dirname "$0")/pristine.sha256"

[ -d "$DST_DIR" ] || { echo "ERROR: $DST_DIR not found — glpi-agent не установлен?" >&2; exit 1; }

fail=0
while read -r hash name; do
    installed="$DST_DIR/$name"
    if [ ! -f "$installed" ]; then
        echo "ERROR: $installed отсутствует в установленном агенте" >&2
        fail=1
        continue
    fi
    actual=$(sha256sum "$installed" | cut -d' ' -f1)
    if [ "$actual" != "$hash" ]; then
        echo "ERROR: апстрим изменил $name (sha256 $actual != ожидаемый $hash)." >&2
        echo "       Сравните новый файл с docker/glpi-agent/mibsupport/$name, перенесите правки" >&2
        echo "       и обновите pristine.sha256." >&2
        fail=1
    fi
done < "$PRISTINE"

[ "$fail" -eq 0 ] || exit 1

for f in "$SRC_DIR"/*.pm; do
    cp "$f" "$DST_DIR/$(basename "$f")"
    echo "patched: $(basename "$f")"
done
