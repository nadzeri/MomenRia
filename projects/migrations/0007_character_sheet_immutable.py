from django.db import migrations


INPUT_FIELDS = ("project_id", "source_id", "version", "mode", "recipe_hash", "input_snapshot", "expires_at")
OUTPUT_FIELDS = ("file", "sha256", "width", "height", "panel_provenance", "synthetic")


def install(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    operator = "IS DISTINCT FROM" if vendor == "postgresql" else "IS NOT"
    inputs = " OR ".join(f"OLD.{name} {operator} NEW.{name}" for name in INPUT_FIELDS)
    outputs = " OR ".join(f"OLD.{name} {operator} NEW.{name}" for name in OUTPUT_FIELDS)
    condition = f"({inputs}) OR (OLD.sha256 <> '' AND ({outputs}))"
    if vendor == "postgresql":
        schema_editor.execute(f"""
            CREATE FUNCTION momenria_protect_character_sheet() RETURNS trigger AS $$
            BEGIN
                IF {condition} THEN RAISE EXCEPTION 'Character sheets are immutable'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER projects_sheet_immutable BEFORE UPDATE ON projects_charactersheet
            FOR EACH ROW EXECUTE FUNCTION momenria_protect_character_sheet();
        """)
    elif vendor == "sqlite":
        schema_editor.execute(f"""
            CREATE TRIGGER projects_sheet_immutable BEFORE UPDATE ON projects_charactersheet
            WHEN {condition}
            BEGIN SELECT RAISE(ABORT, 'Character sheets are immutable'); END;
        """)


def uninstall(apps, schema_editor):
    suffix = " ON projects_charactersheet" if schema_editor.connection.vendor == "postgresql" else ""
    schema_editor.execute(f"DROP TRIGGER IF EXISTS projects_sheet_immutable{suffix}")
    if suffix:
        schema_editor.execute("DROP FUNCTION IF EXISTS momenria_protect_character_sheet()")


class Migration(migrations.Migration):
    dependencies = [("projects", "0006_charactersheet_slotassignment_character_sheet_and_more")]
    operations = [migrations.RunPython(install, uninstall)]
