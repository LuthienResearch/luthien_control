# SQLModel Setup Commands

This file contains the commands to set up and manage the SQLModel database migration.

## Initial Setup

1. Create the new database and set permissions:
```bash
./scripts/create_sqlmodel_db.sh
```

2. Generate the initial migration directly with Alembic:
```bash
poetry run alembic revision --autogenerate -m "Initial SQLModel tables"
```

3. Apply migrations:
```bash
poetry run alembic upgrade head
```

## Common Commands

### Database Management

- Create tables directly using SQLModel (alternative to migrations):
```bash
poetry run python scripts/create_sqlmodel_tables.py
```

- Check current migration version:
```bash
poetry run alembic current
```

- List all migrations:
```bash
poetry run alembic history
```

### Creating New Migrations

After changing models, generate a new migration:

```bash
poetry run python scripts/generate_alembic_migration.py "Description of changes"
```

Or use alembic directly:

```bash
poetry run alembic revision --autogenerate -m "Description of changes"
```

### Applying Migrations

- Apply all pending migrations:
```bash
poetry run alembic upgrade head
```

- Apply specific number of migrations:
```bash
poetry run alembic upgrade +1
```

### Rolling Back Migrations

You can rollback migrations using the `alembic downgrade` command:

- Rollback one migration:
```bash
poetry run alembic downgrade -1
```

- Rollback to a specific revision ID (find IDs with `alembic history`):
```bash
poetry run alembic downgrade <revision_id>
```

- Rollback all migrations (revert to empty database schema):
```bash
poetry run alembic downgrade base
```

- Rollback to the previous database generation:
```bash
poetry run alembic downgrade heads-1
```

### Managing Migrations

- Show the current migration version:
```bash
poetry run alembic current
```

- Show migration history (all revisions):
```bash
poetry run alembic history
```

- Show detailed information about a specific revision:
```bash
poetry run alembic show <revision>
```

- Compare the differences between the database and models (without generating a migration):
```bash
poetry run alembic check
```

- Stamp the database with a specific revision without running migrations:
```bash
poetry run alembic stamp <revision>
```

## Troubleshooting

If you encounter errors about modules not being found, ensure you're running the commands with `poetry run` to use the correct Python environment.

If your database connection fails, check that:
1. The DB_NAME environment variable is set
2. Your database user has the proper permissions
3. The database exists

If you get database schema comparison errors during autogenerate:
1. Make sure your models are properly imported in alembic/env.py
2. Check for dialect-specific column types that might not be recognized
3. Consider using explicit type comparisons in your env.py file