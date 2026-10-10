from django.db import migrations
from django.db.models import Max


def prepare_generation_offer(apps, schema_editor):
    Offer = apps.get_model("catalog", "Offer")
    Offer.objects.filter(purchase_unit="result_download").update(active=False)
    version = max(1, Offer.objects.aggregate(value=Max("version"))["value"] or 1) + 1
    Offer.objects.create(version=version, name="Pembuatan satu foto", price_idr=9900, purchase_unit="generation", active=False)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0009_offer_purchase_unit_and_more")]
    operations = [migrations.RunPython(prepare_generation_offer, migrations.RunPython.noop)]
