# SQLModel & Alembic Database Migration

This document describes the transition from raw SQL with asyncpg to SQLModel (SQLAlchemy + Pydantic) with Alembic for database management.

## Overview

We are transitioning our data persistence layer from direct SQL queries with asyncpg to SQLModel, which combines SQLAlchemy and Pydantic. This approach offers several advantages:

1. **Type safety**: Models serve both as database tables and API schemas
2. **Cleaner code**: ORM queries instead of raw SQL
3. **Migration tracking**: Proper versioning with Alembic
4. **Schema evolution**: Easy schema changes and tracking

## Directory Structure

- `luthien_control/db/sqlmodel_models.py`: SQLModel definitions
- `luthien_control/db/database_async.py`: Async database connection management
- `luthien_control/db/sqlmodel_crud.py`: CRUD operations using SQLModel
- `alembic/`: Migration tracking and scripts
- `scripts/create_sqlmodel_tables.py`: Helper script for initial table creation
- `scripts/generate_alembic_migration.py`: Helper for generating Alembic migrations

## Transition Plan

The transition is designed to be gradual:

1. **Dual systems**: Both old and new systems will coexist temporarily
2. **New database**: The SQLModel system targets a separate DB specified by the `DB_NAME_NEW` environment variable
3. **Feature migration**: Features will be migrated one by one
4. **Data migration**: Once features are migrated, data will be transferred
5. **Cutover**: Final switch to new system with a short downtime

## Using the New System

### Creating Tables

To create the initial tables:

```bash
python scripts/create_sqlmodel_tables.py
```

### Generating Migrations

After changing models, generate migrations with:

```bash
python scripts/generate_alembic_migration.py "Description of changes"
```

### Applying Migrations

Apply pending migrations with:

```bash
alembic upgrade head
```

### Using in Application Code

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.dependencies import get_db
from luthien_control.db.sqlmodel_crud import get_policy_by_name
from luthien_control.db.sqlmodel_models import Policy

@app.get("/policies/{name}")
async def get_policy(name: str, db: AsyncSession = Depends(get_db)):
    policy = await get_policy_by_name(db, name)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy
```

## Testing

Test files will gradually be updated to use the new SQLModel system. During transition, some tests may need to target both systems to ensure correct behavior.

## Environment Setup

To use the new SQLModel system, set the following environment variables:

```bash
# Original database settings (used by legacy code)
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=original_db_name

# New SQLModel database (separate from the original)
DB_NAME_NEW=sqlmodel_db_name
```

The SQLModel system will use all the same connection parameters (user, password, host, port) but connect to the database specified by `DB_NAME_NEW` instead of `DB_NAME`.

> **Note on Backward Compatibility**: For backward compatibility, the system will first check for `DB_NAME_NEW` and fall back to using `DB_NAME` if `DB_NAME_NEW` is not set. This ensures existing tests and code continue to work during the transition period. However, explicitly setting `DB_NAME_NEW` is recommended for clarity.

### Creating the New Database

To create the new database and set up permissions, you can use the provided script:

```bash
# Run the database creation script (will prompt for password if needed)
./scripts/create_sqlmodel_db.sh
```

This script will:
1. Create a new database named by the DB_NAME_NEW variable (defaults to 'luthien_sqlmodel')
2. Grant all necessary permissions to the application user
3. Set up default privileges for future objects

You can customize the database name and user by setting these environment variables before running the script:
- `DB_NAME_NEW`: Name of the new database (default: 'luthien_sqlmodel')
- `APP_USER`: The application user that needs permissions (default: 'luthien')
- `DB_USER`: Admin user to create the database (default: 'postgres')
- `DB_PASSWORD`: Password for the admin user
- `DB_HOST`: Database server hostname (default: 'localhost')
- `DB_PORT`: Database server port (default: '5432')