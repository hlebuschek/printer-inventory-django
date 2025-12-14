"""
Очистка кэша спецификаций моделей принтеров.

Кэш автоматически очищается при изменении/удалении PrinterModelSpec через админку,
но эта команда позволяет очистить его вручную если нужно.

Использование:
    python manage.py clear_spec_cache
"""

from django.core.management.base import BaseCommand
from monthly_report.specs import clear_spec_cache, SPEC_CACHE


class Command(BaseCommand):
    help = 'Очищает кэш спецификаций моделей принтеров'

    def handle(self, *args, **options):
        before_count = len(SPEC_CACHE)

        self.stdout.write("=" * 60)
        self.stdout.write("Очистка кэша PrinterModelSpec")
        self.stdout.write("=" * 60)

        self.stdout.write(f"\nЗаписей в кэше: {before_count}")

        if before_count > 0:
            # Показываем что было в кэше
            self.stdout.write("\nСодержимое кэша:")
            for model_name, spec in list(SPEC_CACHE.items())[:10]:
                if spec:
                    self.stdout.write(
                        f"  - {model_name}: "
                        f"{'цветной' if spec.is_color else 'ч/б'}, "
                        f"{spec.paper_format}, "
                        f"enforce={spec.enforce}"
                    )
                else:
                    self.stdout.write(f"  - {model_name}: None")

            if before_count > 10:
                self.stdout.write(f"  ... и ещё {before_count - 10} записей")

        # Очищаем
        clear_spec_cache()

        after_count = len(SPEC_CACHE)

        self.stdout.write(f"\n✓ Кэш очищен ({before_count} → {after_count})")
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Готово!"))
        self.stdout.write("=" * 60)

        if before_count == 0:
            self.stdout.write(
                self.style.WARNING(
                    "\nПримечание: Кэш уже был пуст. "
                    "Возможно, сервер был недавно перезапущен."
                )
            )
