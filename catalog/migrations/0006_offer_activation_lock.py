from django.db import migrations, models
from django.db.models import F, Q


def mark_active_offers(apps, schema_editor):
    apps.get_model("catalog", "Offer").objects.filter(active=True, activated_at__isnull=True).update(activated_at=F("created_at"))


def install_trigger(apps, schema_editor, permanent=True):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER IF EXISTS catalog_offer_immutable ON catalog_offer")
        guard = "OLD.activated_at IS NOT NULL" if permanent else "OLD.active"
        activation = " OR OLD.activated_at IS DISTINCT FROM NEW.activated_at" if permanent else ""
        schema_editor.execute(f"""
            CREATE OR REPLACE FUNCTION momenria_protect_offer() RETURNS trigger AS $$
            BEGIN
                IF {guard} AND (
                    OLD.version IS DISTINCT FROM NEW.version OR OLD.name IS DISTINCT FROM NEW.name OR
                    OLD.price_idr IS DISTINCT FROM NEW.price_idr{activation}
                ) THEN RAISE EXCEPTION 'Activated offers are immutable'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER catalog_offer_immutable BEFORE UPDATE ON catalog_offer
            FOR EACH ROW EXECUTE FUNCTION momenria_protect_offer();
        """)
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS catalog_offer_immutable")
        guard = "OLD.activated_at IS NOT NULL" if permanent else "OLD.active"
        activation = " OR OLD.activated_at IS NOT NEW.activated_at" if permanent else ""
        schema_editor.execute(f"""
            CREATE TRIGGER catalog_offer_immutable BEFORE UPDATE ON catalog_offer
            WHEN {guard} AND (
                OLD.version IS NOT NEW.version OR OLD.name IS NOT NEW.name OR
                OLD.price_idr IS NOT NEW.price_idr{activation}
            ) BEGIN SELECT RAISE(ABORT, 'Activated offers are immutable'); END;
        """)


def lock_activated_offers(apps, schema_editor):
    install_trigger(apps, schema_editor)


def restore_active_only(apps, schema_editor):
    install_trigger(apps, schema_editor, permanent=False)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_published_template_lifecycle")]
    operations = [
        migrations.AddField(model_name="offer", name="activated_at", field=models.DateTimeField(blank=True, editable=False, null=True)),
        migrations.RunPython(mark_active_offers, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="offer", constraint=models.CheckConstraint(condition=Q(active=False) | Q(activated_at__isnull=False), name="catalog_active_offer_has_activation")),
        migrations.RunPython(lock_activated_offers, restore_active_only),
    ]
