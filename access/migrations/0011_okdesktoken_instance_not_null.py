import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("access", "0010_okdesktoken_default_instance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userokdesktoken",
            name="instance",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_tokens",
                to="integrations.okdeskinstance",
                verbose_name="Инстанс Okdesk",
            ),
        ),
    ]
