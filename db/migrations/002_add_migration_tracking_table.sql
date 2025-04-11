-- db/migrations/002_add_migration_tracking_table.sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE schema_migrations IS 'Tracks the version of applied database migrations.';
COMMENT ON COLUMN schema_migrations.version IS 'The unique version identifier for the migration (e.g., the filename).';
COMMENT ON COLUMN schema_migrations.applied_at IS 'Timestamp when the migration was applied.';