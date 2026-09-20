# Database foundation

Phase 1A provides the PostgreSQL persistence foundation. SQLAlchemy models live
under `apps/api/app/models`, while Alembic configuration and migrations live
here.

## Planned architecture

- `alembic.ini` and `migrations/env.py` for environment-driven migrations.
- Initial migration `1a8fd5c3debf` for organizations, users/roles, devices,
  incidents, diagnostic records, recommendations, repair actions, escalations,
  and audit events.
- Seed directory for controlled reference data.
- Environment-driven configuration using `DATABASE_URL`; importing the API does
  not connect to the database.

## Future work

Run `alembic upgrade head` from the repository root after setting
`DATABASE_URL=postgresql+psycopg://...`. SQLite-compatible schema and lifecycle
tests run with `pytest apps/api/tests`. PostgreSQL integration tests require a
separate `TEST_DATABASE_URL` pointing to an isolated test database.

Use a separate database URL for tests; the test suite creates an isolated
in-memory SQLite database and never connects to the configured development
database. Production backup, restore, retention, and recovery procedures must
be established before production data is introduced.
