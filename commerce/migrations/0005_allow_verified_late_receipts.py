from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("commerce", "0004_alter_refund_requested_by")]

    operations = [
        migrations.RemoveConstraint(model_name="order", name="commerce_one_active_order_per_result"),
        migrations.AddConstraint(model_name="order", constraint=models.UniqueConstraint(fields=("owner", "result_id_snapshot"), condition=models.Q(payment_state__in=("creating", "pending", "uncertain")), name="commerce_one_active_order_per_result")),
    ]
