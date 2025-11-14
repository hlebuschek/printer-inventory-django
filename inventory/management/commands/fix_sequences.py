from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Fix all PostgreSQL sequences to match MAX(id) values'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Получаем список всех таблиц с последовательностями
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_get_serial_sequence(schemaname||'.'||tablename, 'id') as sequence_name
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                AND pg_get_serial_sequence(schemaname||'.'||tablename, 'id') IS NOT NULL
                AND tablename != 'django_session'
                ORDER BY tablename
            """)

            tables = cursor.fetchall()

            for schema, table, sequence in tables:
                if sequence:
                    # Получаем максимальный ID
                    cursor.execute(f'SELECT COALESCE(MAX(id), 0) FROM {schema}.{table}')
                    max_id = cursor.fetchone()[0]

                    # Устанавливаем значение последовательности
                    if max_id == 0:
                        max_id = 1

                    cursor.execute(f"SELECT setval('{sequence}', {max_id})")

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Исправлено: {schema}.{table} → {sequence} (значение: {max_id})'
                        )
                    )

        self.stdout.write(self.style.SUCCESS('\n✓ Все последовательности успешно исправлены!'))