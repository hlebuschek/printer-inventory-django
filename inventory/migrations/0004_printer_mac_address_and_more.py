# Generated by Django 5.2.4 on 2025-07-05 08:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_alter_pagecounter_options_pagecounter_drum_black_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='printer',
            name='mac_address',
            field=models.CharField(blank=True, db_index=True, max_length=17, null=True, unique=True, verbose_name='MAC-адрес'),
        ),
        migrations.AddIndex(
            model_name='printer',
            index=models.Index(fields=['mac_address'], name='inventory_p_mac_add_fc8d1e_idx'),
        ),
    ]
