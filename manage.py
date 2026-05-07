#!/usr/bin/env python
import os
import sys

# На Windows консольная кодировка по умолчанию cp1251 — любой Unicode-символ
# (например, ✓ в celery init logger) ломает StreamHandler с UnicodeEncodeError
# и засоряет вывод трейсом. Переключаем stdout/stderr в UTF-8 явно.
# Эквивалент `set PYTHONIOENCODING=utf-8`, но не требует ручного выставления.
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "printer_inventory.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django, ensure it's installed") from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
