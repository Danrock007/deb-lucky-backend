from django.db import migrations, models


def empty_references_to_null(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Order.objects.filter(payment_reference="").update(payment_reference=None)


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_order_customer_name_order_payment_reference_and_more"),
    ]

    operations = [
        migrations.RunPython(empty_references_to_null, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="payment_reference",
            field=models.CharField(
                blank=True,
                default=None,
                max_length=120,
                null=True,
                unique=True,
            ),
        ),
    ]
