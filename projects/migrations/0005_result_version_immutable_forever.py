from django.db import migrations


POSTGRES_BODY = """
    OLD.project_id IS DISTINCT FROM NEW.project_id OR OLD.parent_id IS DISTINCT FROM NEW.parent_id OR
    OLD.generation_root_id IS DISTINCT FROM NEW.generation_root_id OR OLD.source_snapshot IS DISTINCT FROM NEW.source_snapshot OR
    OLD.region_snapshot IS DISTINCT FROM NEW.region_snapshot OR OLD.configuration_hash IS DISTINCT FROM NEW.configuration_hash OR
    OLD.kind IS DISTINCT FROM NEW.kind OR OLD.greeting IS DISTINCT FROM NEW.greeting OR
    OLD.number IS DISTINCT FROM NEW.number OR OLD.synthetic IS DISTINCT FROM NEW.synthetic OR OLD.expires_at IS DISTINCT FROM NEW.expires_at
"""

SQLITE_BODY = """
    OLD.project_id IS NOT NEW.project_id OR OLD.parent_id IS NOT NEW.parent_id OR
    OLD.generation_root_id IS NOT NEW.generation_root_id OR OLD.source_snapshot IS NOT NEW.source_snapshot OR
    OLD.region_snapshot IS NOT NEW.region_snapshot OR OLD.configuration_hash IS NOT NEW.configuration_hash OR
    OLD.kind IS NOT NEW.kind OR OLD.greeting IS NOT NEW.greeting OR OLD.number IS NOT NEW.number OR
    OLD.synthetic IS NOT NEW.synthetic OR OLD.expires_at IS NOT NEW.expires_at
"""


def install(apps, schema_editor, ready_only=False):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER IF EXISTS projects_result_immutable ON projects_resultversion")
        condition = f"OLD.status = 'ready' AND ({POSTGRES_BODY})" if ready_only else f"({POSTGRES_BODY})"
        schema_editor.execute(f"""
            CREATE OR REPLACE FUNCTION momenria_protect_result() RETURNS trigger AS $$
            BEGIN
                IF {condition} THEN RAISE EXCEPTION 'Result versions are immutable'; END IF;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
            CREATE TRIGGER projects_result_immutable BEFORE UPDATE ON projects_resultversion
            FOR EACH ROW EXECUTE FUNCTION momenria_protect_result();
        """)
    elif schema_editor.connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS projects_result_immutable")
        condition = f"OLD.status = 'ready' AND ({SQLITE_BODY})" if ready_only else f"({SQLITE_BODY})"
        schema_editor.execute(f"""
            CREATE TRIGGER projects_result_immutable BEFORE UPDATE ON projects_resultversion
            WHEN {condition}
            BEGIN SELECT RAISE(ABORT, 'Result versions are immutable'); END;
        """)


def make_immutable(apps, schema_editor):
    install(apps, schema_editor)


def restore_ready_only(apps, schema_editor):
    install(apps, schema_editor, ready_only=True)


class Migration(migrations.Migration):
    dependencies = [("projects", "0004_immutable_records")]
    operations = [migrations.RunPython(make_immutable, restore_ready_only)]
