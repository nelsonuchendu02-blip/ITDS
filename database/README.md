# Database foundation

This repository prepares PostgreSQL support without introducing application data models or production tables in Phase 0.

## Planned architecture

- Migrations directory for future schema evolution.
- Seed directory for controlled reference data.
- Environment-driven configuration using `DATABASE_URL`.

## Future work

The database layer will be introduced in later phases with a clear schema designed for support, diagnostics, incident, and automation data.
