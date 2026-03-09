# Database Migration Guide

This project uses Alembic for database migrations.

## Setup

Alembic is already configured. The configuration files are:
- `alembic.ini` - Alembic configuration
- `alembic/env.py` - Migration environment setup
- `alembic/versions/` - Directory containing migration scripts

## Common Commands

### Create a new migration

When you add a new field to a model:

```bash
# Auto-generate migration based on model changes
alembic revision --autogenerate -m "description of changes"

# Or create an empty migration to write manually
alembic revision -m "description of changes"
```

### Apply migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply migrations up to a specific revision
alembic upgrade <revision>

# Apply next migration only
alembic upgrade +1
```

### Rollback migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to a specific revision
alembic downgrade <revision>

# Rollback all migrations
alembic downgrade base
```

### Check migration status

```bash
# Show current revision
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic heads
```

## Adding a New Field to a Table

1. **Add the field to the SQLAlchemy model** in `app/db/sqlalchemy_models.py`:
   ```python
   class Team(Base):
       # ... existing fields ...
       new_field = Column(String, nullable=True)
   ```

2. **Generate a migration**:
   ```bash
   alembic revision --autogenerate -m "add new_field to team"
   ```

3. **Review the generated migration** in `alembic/versions/` to ensure it's correct

4. **Apply the migration**:
   ```bash
   alembic upgrade head
   ```

## Example: Adding the Coach Field

The coach field has already been added. To apply the migration:

```bash
alembic upgrade head
```

This will add the `coach` column to the `team` table if it doesn't exist.

## Important Notes

- Always review auto-generated migrations before applying them
- Test migrations on a development database first
- Keep migrations small and focused on one change
- Never edit existing migrations that have been applied to production
- Create a new migration if you need to change something that's already been applied

## Troubleshooting

### Migration conflicts
If you have conflicts between branches:
```bash
# Merge the branches
alembic merge -m "merge branches" <revision1> <revision2>
```

### Database out of sync
If your database is out of sync with migrations:
```bash
# Check current state
alembic current

# Stamp to a specific revision (use with caution)
alembic stamp <revision>
```
