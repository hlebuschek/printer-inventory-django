# Generated manually to support negative values in total_prints

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monthly_report', '0004_monthlyreport_a3_bw_end_manual_and_more'),
    ]

    operations = [
        # Сначала удаляем CHECK constraint, созданный PositiveIntegerField
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    -- Пытаемся удалить constraint, если он существует
                    -- Имя constraint генерируется Django автоматически
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conrelid = 'monthly_report_monthlyreport'::regclass
                        AND conname LIKE '%total_prints%check%'
                    ) THEN
                        EXECUTE (
                            SELECT 'ALTER TABLE monthly_report_monthlyreport DROP CONSTRAINT ' || conname || ';'
                            FROM pg_constraint
                            WHERE conrelid = 'monthly_report_monthlyreport'::regclass
                            AND conname LIKE '%total_prints%check%'
                            LIMIT 1
                        );
                    END IF;
                END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Затем меняем тип поля
        migrations.AlterField(
            model_name='monthlyreport',
            name='total_prints',
            field=models.IntegerField(default=0, verbose_name='Итого отпечатков шт.'),
        ),
    ]
