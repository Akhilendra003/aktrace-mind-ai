# AkTrace Mind AI backend — Phase 2

Python 3.12, FastAPI, pydantic-settings, SQLAlchemy 2.x, psycopg 3.
No application tables, models, or migrations are created.

## Local setup (PowerShell)

```powershell
cd C:\Users\91638\Desktop\aktrace-mind-ai\backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (!(Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
notepad .env
```

Set `DB_NAME`, `DB_USER`, and `DB_PASSWORD` for the application.
The existing local `.env` was initialized with a randomly generated application
password; preserve it when using the setup command below. The version-control-safe example
contains placeholders only. Never commit `.env` or paste credentials into logs.
For fresh checkouts, replace the example password before provisioning.
Environment variables override `.env`; restart the backend after settings change.
The `.env` path is resolved relative to the backend directory, independent of cwd.

## Create the PostgreSQL role and database

PostgreSQL 17 is already installed locally. Check its Windows service:

```powershell
Get-Service postgresql-x64-17
# Only if stopped; run in an elevated PowerShell:
Start-Service postgresql-x64-17
```

Run the provisioning utility with the existing PostgreSQL administrator account:

```powershell
.\.venv\Scripts\python.exe -m app.db.setup --admin-user postgres
```

The utility prompts privately for the existing administrator password. It creates
the configured application login (not a superuser) and database owned by that login.
It does not change existing roles, passwords, database ownership, or tables.
The app uses `DB_USER`, not the administrator account. Admin access is needed only
for setup. If provisioning partially succeeds, rerun after resolving the failure;
existing resources are preserved. A successful setup message must be followed by
the connection check below, especially if a role already existed.

## Verify connectivity and start

```powershell
.\.venv\Scripts\python.exe -m app.db.check
$LASTEXITCODE  # 0 = connected, 1 = unavailable/invalid configuration
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

From another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/health/db
```

- `/` and `/health` preserve Phase 1 responses; they do not require a live database.
- `/health/db` executes `SELECT 1`: HTTP 200 when connected, generic HTTP 503 on
  connection/query/pool failures. Connection details are never sent to clients.
- Swagger: `http://127.0.0.1:8000/docs`.
- Invalid environment configuration stops startup with a sanitized message.
- Valid configuration with an unreachable database allows startup and liveness.

## Tests

Run these from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

Unit tests use isolated settings and mocks; they do not prove PostgreSQL is reachable.
The real read-only database test is opt-in and fails if the configured connection fails:

```powershell
$env:RUN_DATABASE_TESTS = "1"
try { .\.venv\Scripts\python.exe -m pytest -q } finally {
    Remove-Item Env:RUN_DATABASE_TESTS -ErrorAction SilentlyContinue
}
```

## Runtime behavior

Startup loads validated settings and creates a lazy engine/session factory.
Each DB request receives its own session through `Depends(get_session)`.
Sessions close after requests, roll back unfinished transactions, and return
connections to the pool. Future writes must explicitly commit. Shutdown disposes
the engine. No database connection is opened merely by importing the app.

Defaults per worker: pool size 5, overflow 5 (10 maximum simultaneous connections),
pool wait 5 seconds, connect timeout 5 seconds, statement timeout 5 seconds, recycle
after 1800 seconds, and pre-ping on checkout. These are configurable; four workers
can open up to 40 connections. Timeouts apply to separate stages, not a strict
end-to-end request deadline. `DB_SSLMODE=prefer` suits local development; use
`verify-full` with a trusted certificate setup for remote production connections.

Call → FastAPI app → route/dependency resolution → session → pooled connection
→ psycopg → PostgreSQL `SELECT 1` → result → JSON response → session cleanup.
