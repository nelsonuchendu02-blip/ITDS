# ITDS

IT Support Diagnostic System (ITDS) is a foundation for secure, modular support tooling for Windows endpoints. This repository establishes the engineering baseline for a future IT operations platform covering monitoring, diagnostics, remediation, incident handling, and documentation.

## Purpose

This Phase 0 release focuses on the repository foundation and safe extensibility rather than production diagnostics or endpoint automation. The system is intentionally constrained to a clean backend/frontend structure, security baseline, and validation pipeline.

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

- `apps/api` exposes the FastAPI backend and health endpoint
- `apps/web` hosts a Vite + React + TypeScript frontend shell
- `apps/agent` defines the future Windows endpoint agent architecture
- `database` holds migration and seed structure for PostgreSQL support
- `automation/powershell` defines standards for safe PowerShell automation
- `docs` documents architecture, API, security, and operating assumptions
- `tests` contains validation for backend and frontend foundation checks

## Technology stack

- Frontend: React, TypeScript, Vite
- Backend: Python, FastAPI
- Database: PostgreSQL planning only for Phase 0
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

Phase 0: engineering foundation only.

## Known limitations

- No real-time monitoring implementation
- No device discovery or endpoint automation
- No production PostgreSQL schema beyond the planned foundation
- No deployment infrastructure
- No real user authentication or RBAC beyond baseline security documentation

## Recommended commit message

`feat: establish ITDS production foundation`
