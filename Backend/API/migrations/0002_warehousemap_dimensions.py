from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("API", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="warehousemap",
            name="aisle_count",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="warehousemap",
            name="shelves_per_aisle",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
