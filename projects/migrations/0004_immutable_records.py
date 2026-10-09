from django.db import migrations


def create_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION momenria_protect_template() RETURNS trigger AS $$
            BEGIN
                IF OLD.status IN ('published', 'paused') AND (
                    OLD.slug IS DISTINCT FROM NEW.slug OR OLD.version IS DISTINCT FROM NEW.version OR
                    OLD.name IS DISTINCT FROM NEW.name OR OLD.people_count IS DISTINCT FROM NEW.people_count OR
                    OLD.sample_asset IS DISTINCT FROM NEW.sample_asset OR OLD.sample_sha256 IS DISTINCT FROM NEW.sample_sha256 OR
                    OLD.asset_width IS DISTINCT FROM NEW.asset_width OR OLD.asset_height IS DISTINCT FROM NEW.asset_height OR
                    OLD.coordinate_convention IS DISTINCT FROM NEW.coordinate_convention OR
                    OLD.configuration_hash IS DISTINCT FROM NEW.configuration_hash OR OLD.generation_config IS DISTINCT FROM NEW.generation_config
                ) THEN RAISE EXCEPTION 'Published template versions are immutable'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER catalog_template_immutable BEFORE UPDATE ON catalog_templateversion
            FOR EACH ROW EXECUTE FUNCTION momenria_protect_template();

            CREATE FUNCTION momenria_protect_result() RETURNS trigger AS $$
            BEGIN
                IF OLD.status = 'ready' AND (
                    OLD.project_id IS DISTINCT FROM NEW.project_id OR OLD.parent_id IS DISTINCT FROM NEW.parent_id OR
                    OLD.generation_root_id IS DISTINCT FROM NEW.generation_root_id OR OLD.source_snapshot IS DISTINCT FROM NEW.source_snapshot OR
                    OLD.region_snapshot IS DISTINCT FROM NEW.region_snapshot OR OLD.configuration_hash IS DISTINCT FROM NEW.configuration_hash OR
                    OLD.kind IS DISTINCT FROM NEW.kind OR OLD.greeting IS DISTINCT FROM NEW.greeting OR
                    OLD.number IS DISTINCT FROM NEW.number OR OLD.synthetic IS DISTINCT FROM NEW.synthetic OR OLD.expires_at IS DISTINCT FROM NEW.expires_at
                ) THEN RAISE EXCEPTION 'Ready result versions are immutable'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER projects_result_immutable BEFORE UPDATE ON projects_resultversion
            FOR EACH ROW EXECUTE FUNCTION momenria_protect_result();

            CREATE FUNCTION momenria_protect_slot() RETURNS trigger AS $$
            BEGIN
                IF EXISTS (SELECT 1 FROM catalog_templateversion WHERE id = OLD.template_id AND status IN ('published', 'paused')) THEN
                    RAISE EXCEPTION 'Published face slots are immutable';
                END IF;
                RETURN OLD;
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER catalog_slot_immutable_update BEFORE UPDATE ON catalog_faceslot
            FOR EACH ROW EXECUTE FUNCTION momenria_protect_slot();
            CREATE TRIGGER catalog_slot_immutable_delete BEFORE DELETE ON catalog_faceslot
            FOR EACH ROW EXECUTE FUNCTION momenria_protect_slot();

            CREATE FUNCTION momenria_protect_offer() RETURNS trigger AS $$
            BEGIN
                IF OLD.active AND (
                    OLD.version IS DISTINCT FROM NEW.version OR OLD.name IS DISTINCT FROM NEW.name OR OLD.price_idr IS DISTINCT FROM NEW.price_idr
                ) THEN RAISE EXCEPTION 'Active offers are immutable'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER catalog_offer_immutable BEFORE UPDATE ON catalog_offer
            FOR EACH ROW EXECUTE FUNCTION momenria_protect_offer();
        """)
    elif vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER catalog_template_immutable BEFORE UPDATE ON catalog_templateversion
            WHEN OLD.status IN ('published', 'paused') AND (
                OLD.slug IS NOT NEW.slug OR OLD.version IS NOT NEW.version OR OLD.name IS NOT NEW.name OR
                OLD.people_count IS NOT NEW.people_count OR OLD.sample_asset IS NOT NEW.sample_asset OR
                OLD.sample_sha256 IS NOT NEW.sample_sha256 OR OLD.asset_width IS NOT NEW.asset_width OR
                OLD.asset_height IS NOT NEW.asset_height OR OLD.coordinate_convention IS NOT NEW.coordinate_convention OR
                OLD.configuration_hash IS NOT NEW.configuration_hash OR OLD.generation_config IS NOT NEW.generation_config
            ) BEGIN SELECT RAISE(ABORT, 'Published template versions are immutable'); END;
        """)
        schema_editor.execute("""
            CREATE TRIGGER projects_result_immutable BEFORE UPDATE ON projects_resultversion
            WHEN OLD.status = 'ready' AND (
                OLD.project_id IS NOT NEW.project_id OR OLD.parent_id IS NOT NEW.parent_id OR
                OLD.generation_root_id IS NOT NEW.generation_root_id OR OLD.source_snapshot IS NOT NEW.source_snapshot OR
                OLD.region_snapshot IS NOT NEW.region_snapshot OR OLD.configuration_hash IS NOT NEW.configuration_hash OR
                OLD.kind IS NOT NEW.kind OR OLD.greeting IS NOT NEW.greeting OR OLD.number IS NOT NEW.number OR
                OLD.synthetic IS NOT NEW.synthetic OR OLD.expires_at IS NOT NEW.expires_at
            ) BEGIN SELECT RAISE(ABORT, 'Ready result versions are immutable'); END;
        """)
        schema_editor.execute("""
            CREATE TRIGGER catalog_slot_immutable_update BEFORE UPDATE ON catalog_faceslot
            WHEN EXISTS (SELECT 1 FROM catalog_templateversion WHERE id = OLD.template_id AND status IN ('published', 'paused'))
            BEGIN SELECT RAISE(ABORT, 'Published face slots are immutable'); END;
        """)
        schema_editor.execute("""
            CREATE TRIGGER catalog_slot_immutable_delete BEFORE DELETE ON catalog_faceslot
            WHEN EXISTS (SELECT 1 FROM catalog_templateversion WHERE id = OLD.template_id AND status IN ('published', 'paused'))
            BEGIN SELECT RAISE(ABORT, 'Published face slots are immutable'); END;
        """)
        schema_editor.execute("""
            CREATE TRIGGER catalog_offer_immutable BEFORE UPDATE ON catalog_offer
            WHEN OLD.active AND (OLD.version IS NOT NEW.version OR OLD.name IS NOT NEW.name OR OLD.price_idr IS NOT NEW.price_idr)
            BEGIN SELECT RAISE(ABORT, 'Active offers are immutable'); END;
        """)


def drop_triggers(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    for name in ("catalog_template_immutable", "projects_result_immutable", "catalog_slot_immutable_update", "catalog_slot_immutable_delete", "catalog_offer_immutable"):
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {name}" + (" ON catalog_templateversion" if vendor == "postgresql" and name == "catalog_template_immutable" else " ON projects_resultversion" if vendor == "postgresql" and name == "projects_result_immutable" else " ON catalog_faceslot" if vendor == "postgresql" and name.startswith("catalog_slot") else " ON catalog_offer" if vendor == "postgresql" else ""))
    if vendor == "postgresql":
        for name in ("momenria_protect_template", "momenria_protect_result", "momenria_protect_slot", "momenria_protect_offer"):
            schema_editor.execute(f"DROP FUNCTION IF EXISTS {name}()")


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_faceslot_catalog_slot_size_normalized_and_more"), ("projects", "0003_sourceasset_thumbnail_sourceasset_thumbnail_sha256")]
    operations = [migrations.RunPython(create_triggers, drop_triggers)]
