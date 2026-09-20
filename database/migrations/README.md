# Database migrations

The migrations directory contains the Phase 1A PostgreSQL schema and lifecycle.

The initial Phase 1A migration is
`versions/1a8fd5c3debf_create_phase_1a_database_foundation.py`.
Set `DATABASE_URL` and run `alembic upgrade head` from the repository root.
Fast unit tests use an in-memory SQLite database. PostgreSQL integration tests
require an isolated PostgreSQL instance and the `psycopg` dependency; they are
skipped unless `TEST_DATABASE_URL` or `DATABASE_URL` explicitly points to
PostgreSQL. Run `pytest apps/api/tests -m postgresql` to exercise migrations,
relationships, constraints, UUIDs, timestamps, JSON, and foreign keys.
