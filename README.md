# ITDS

IT Support Diagnostic System (ITDS) is a foundation for secure, modular support tooling for Windows endpoints. This repository establishes the engineering baseline for a future IT operations platform covering monitoring, diagnostics, remediation, incident handling, and documentation.

## Purpose

ITDS is implemented in phased increments. The current repository state includes
an operational backend API surface, a secure read-only endpoint-agent
foundation, and a live-data operations dashboard frontend.

## System capabilities

Planned capabilities in future phases include:

- real-time IT monitoring
- device discovery
- system diagnostics
- root-cause analysis
- recommendation workflows
- repair and remediation
- incident management
- escalation and documentation
- automation with Windows endpoints

## Architecture overview

The repository separates responsibilities across application domains:

- `apps/api` exposes the FastAPI backend and versioned operational APIs
- `apps/web` hosts a permission-aware Vite + React + TypeScript operations dashboard
- `apps/agent` provides the Phase 1M read-only Windows endpoint agent foundation
- `database` holds migration and seed structure for PostgreSQL support
- `automation/powershell` defines standards for safe PowerShell automation
- `docs` documents architecture, API, security, and operating assumptions
- `tests` contains validation for backend and frontend foundation checks

## Technology stack

- Frontend: React, TypeScript, Vite
- Backend: Python, FastAPI
- Database: SQLAlchemy ORM and Alembic migrations targeting PostgreSQL
- Endpoint automation: Python agent + PowerShell conventions
- CI/CD: GitHub Actions
- Security: environment-based settings and structured logging

## Repository structure

```text
ITDS/
├── apps/
│   ├── api/
│   ├── web/
│   └── agent/
├── packages/
│   └── shared/
├── automation/
│   └── powershell/
├── database/
│   ├── migrations/
│   └── seed/
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── security/
│   └── operations/
├── tests/
│   ├── integration/
│   └── e2e/
├── scripts/
├── .github/
│   └── workflows/
├── .gitignore
├── .env.example
├── README.md
├── LICENSE
└── requirements.txt
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm
- PostgreSQL client tooling for future integration
- Git

## Local setup

1. Clone the repository.
2. Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install backend dependencies:

```bash
pip install -r apps/api/requirements.txt
```

4. Copy the environment sample:

```bash
cp .env.example .env
```

5. Install frontend dependencies:

```bash
cd apps/web
npm install
```

## Configuration

The project uses environment variables and excludes secrets from Git. The sample file at `.env.example` defines the expected keys. Update `.env` locally with your settings and never commit secrets.

## Backend startup

```bash
cd apps/api
uvicorn app.main:app --reload
```

The backend exposes a structured health check at `/api/health`.

## Frontend startup

```bash
cd apps/web
npm run dev
```

The frontend reads `VITE_API_BASE_URL` from environment variables and uses the backend health endpoint for operational status.

## Test instructions

```bash
pytest apps/api/tests
cd apps/web && npm install && npm run build
```

## Security guidance

- Do not commit `.env` files or real credentials.
- Keep secrets in environment variables only.
- Prefer explicit configuration over broad defaults.
- Validate user input and avoid wildcard CORS in production.
- Apply secure logging and structured error responses.

## Git workflow

- Keep work on the `main` branch for the Phase 0 foundation.
- Use small, reviewable commits.
- Do not force push or rewrite shared history.

## Current development phase

Phase 1N: operations dashboard implementation on top of established backend,
monitoring, incident, agent, diagnostics, and remediation foundations.

### Database validation

SQLite is used by the fast unit tests (`pytest apps/api/tests -m
"not postgresql"`), so they run without external services. PostgreSQL
integration tests are a separate path and are skipped unless
`TEST_DATABASE_URL` explicitly contains a PostgreSQL URL; they never silently
connect to a local or development database. Run them with
`pytest apps/api/tests -m postgresql` after providing an isolated test
database. The integration path exercises the Alembic upgrade/downgrade
lifecycle, relationships, constraints, UUIDs, timestamps, JSON, and foreign
keys.

## Known limitations

- No deployment infrastructure in this repository
- Polling-based UI refresh (no websocket streaming layer yet)
- Token lifecycle is session-memory only on the frontend (no refresh-token flow)
- Production operations hardening and runbook automation are still iterative

## Recommended commit message

`feat: establish ITDS production foundation`
