import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0014_okdesk_default_instance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="okdeskissue",
            name="instance",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="issues",
                to="integrations.okdeskinstance",
                verbose_name="Инстанс Okdesk",
            ),
        ),
        migrations.AlterField(
            model_name="okdeskcomment",
            name="instance",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="comments",
                to="integrations.okdeskinstance",
                verbose_name="Инстанс Okdesk",
            ),
        ),
    ]
