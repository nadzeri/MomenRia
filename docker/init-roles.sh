#!/bin/sh
set -eu

psql --dbname "$DATABASE_NAME" --set ON_ERROR_STOP=1 \
  --set database_name="$DATABASE_NAME" \
  --set migration_user="$MIGRATION_DB_USER" \
  --set migration_password="$MIGRATION_DB_PASSWORD" \
  --set runtime_user="$RUNTIME_DB_USER" \
  --set runtime_password="$RUNTIME_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'migration_user', :'migration_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'migration_user') \gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'runtime_user', :'runtime_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'runtime_user') \gexec

GRANT CONNECT ON DATABASE :"database_name" TO :"migration_user", :"runtime_user";
GRANT USAGE, CREATE ON SCHEMA public TO :"migration_user";
GRANT USAGE ON SCHEMA public TO :"runtime_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"migration_user" IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"runtime_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"migration_user" IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO :"runtime_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"runtime_user";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"runtime_user";
SQL
