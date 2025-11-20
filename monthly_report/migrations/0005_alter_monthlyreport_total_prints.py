# Generated manually to support negative values in total_prints

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monthly_report', '0004_monthlyreport_a3_bw_end_manual_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='monthlyreport',
            name='total_prints',
            field=models.IntegerField(default=0, verbose_name='Итого отпечатков шт.'),
        ),
    ]
