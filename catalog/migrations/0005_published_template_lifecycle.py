from django.db import migrations


POSTGRES_BODY = """
    OLD.slug IS DISTINCT FROM NEW.slug OR OLD.version IS DISTINCT FROM NEW.version OR
    OLD.name IS DISTINCT FROM NEW.name OR OLD.people_count IS DISTINCT FROM NEW.people_count OR
    OLD.sample_asset IS DISTINCT FROM NEW.sample_asset OR OLD.sample_sha256 IS DISTINCT FROM NEW.sample_sha256 OR
    OLD.asset_width IS DISTINCT FROM NEW.asset_width OR OLD.asset_height IS DISTINCT FROM NEW.asset_height OR
    OLD.coordinate_convention IS DISTINCT FROM NEW.coordinate_convention OR
    OLD.configuration_hash IS DISTINCT FROM NEW.configuration_hash OR OLD.generation_config IS DISTINCT FROM NEW.generation_config
"""

SQLITE_BODY = """
    OLD.slug IS NOT NEW.slug OR OLD.version IS NOT NEW.version OR OLD.name IS NOT NEW.name OR
    OLD.people_count IS NOT NEW.people_count OR OLD.sample_asset IS NOT NEW.sample_asset OR
    OLD.sample_sha256 IS NOT NEW.sample_sha256 OR OLD.asset_width IS NOT NEW.asset_width OR
    OLD.asset_height IS NOT NEW.asset_height OR OLD.coordinate_convention IS NOT NEW.coordinate_convention OR
    OLD.configuration_hash IS NOT NEW.configuration_hash OR OLD.generation_config IS NOT NEW.generation_config
"""


def install(apps, schema_editor, block_draft=True):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER IF EXISTS catalog_template_immutable ON catalog_templateversion")
        draft = "OLD.status IN ('published', 'paused') AND NEW.status = 'draft' OR " if block_draft else ""
        schema_editor.execute(f"""
            CREATE OR REPLACE FUNCTION momenria_protect_template() RETURNS trigger AS $$
            BEGIN
                IF {draft}OLD.status IN ('published', 'paused') AND ({POSTGRES_BODY})
                THEN RAISE EXCEPTION 'Published template versions are immutable'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER catalog_template_immutable BEFORE UPDATE ON catalog_templateversion
            FOR EACH ROW EXECUTE FUNCTION momenria_protect_template();
        """)
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS catalog_template_immutable")
        draft = "OLD.status IN ('published', 'paused') AND NEW.status = 'draft' OR " if block_draft else ""
        schema_editor.execute(f"""
            CREATE TRIGGER catalog_template_immutable BEFORE UPDATE ON catalog_templateversion
            WHEN {draft}OLD.status IN ('published', 'paused') AND ({SQLITE_BODY})
            BEGIN SELECT RAISE(ABORT, 'Published template versions are immutable'); END;
        """)


def block_draft(apps, schema_editor):
    install(apps, schema_editor)


def allow_draft(apps, schema_editor):
    install(apps, schema_editor, block_draft=False)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0004_faceslot_catalog_slot_size_normalized_and_more"), ("projects", "0004_immutable_records")]
    operations = [migrations.RunPython(block_draft, allow_draft)]
