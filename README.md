# Invoice Processor

OCR-powered invoice data extraction using DocWise, FastAPI, React, and Azure.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (React + Vite + Tailwind)                          │
│  - MSAL authentication (Azure Entra ID)                     │
│  - Upload / Bulk Upload / Jobs / Logs / Dashboard pages     │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS + Bearer token
┌──────────────────────────▼──────────────────────────────────┐
│  FastAPI Backend (Python 3.12)                              │
│  - Entra auth middleware (JWT decode, no sig verification)  │
│  - /api/invoices  — upload, bulk-upload, list, delete       │
│  - /jobs          — job status, paged listing               │
│  - /logs          — audit log, diagnostics                  │
│  - /api/dashboard — KPIs, recent activity                   │
└───────┬─────────────────────┬───────────────────────────────┘
        │                     │
┌───────▼──────┐    ┌─────────▼──────────┐
│  PostgreSQL  │    │  Azure Blob Storage │
│  (psycopg2)  │    │  Container: invoices│
│  jobs        │    │  SAS URLs on demand │
│  logs        │    └────────────────────┘
│  invoices    │
└──────────────┘
        │
┌───────▼──────────────┐
│  DocWise API         │
│  Invoice OCR + text  │
│  extraction          │
└──────────────────────┘
```

## Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 14+
- [Poetry](https://python-poetry.org/)
- Azure Storage Account (optional for file storage)
- Azure Entra ID app registration (optional, disable with `SKIP_AUTH=true`)

## Backend Setup

```bash
cd backend
poetry install
cp .env.example .env
# Edit .env with your credentials
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env
# Edit .env with VITE_ENTRA_CLIENT_ID and VITE_ENTRA_TENANT_ID
npm run dev
```

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_HOST` | PostgreSQL hostname | `localhost` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | Database name | `invoice_processor` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | _(empty)_ |
| `POSTGRES_SCHEMA` | Schema name | `public` |
| `POSTGRES_SSLMODE` | SSL mode | `prefer` |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob connection string | _(empty)_ |
| `DOCWISE_API_KEY` | DocWise API key | _(empty)_ |
| `SKIP_AUTH` | Bypass auth (dev only) | `false` |
| `ALLOW_DEV_AUTH` | Allow `dev-token` header | `false` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated CORS origins | `http://localhost:5173` |
| `DOCWISE_MAX_ATTEMPTS` | OCR retry attempts | `3` |
| `DOCWISE_BACKOFF_BASE_SEC` | Retry backoff base (seconds) | `2` |
| `DOCWISE_TIMEOUT_SEC` | OCR request timeout (seconds) | `120` |
| `DOCWISE_URL` | DocWise API endpoint URL | `https://docwiseapi-dev.getinge.com/v1/docwise/analyze` |

### Frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `VITE_ENTRA_CLIENT_ID` | Azure Entra app client ID |
| `VITE_ENTRA_TENANT_ID` | Azure Entra tenant ID |
| `VITE_API_BASE_URL` | Backend API URL (default: empty, uses Vite proxy) |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check with DB status |
| `GET` | `/auth/me` | Current user info |
| `POST` | `/auth/verify-token` | Validate a Bearer token |
| `POST` | `/api/invoices/upload` | Single PDF invoice upload + OCR |
| `POST` | `/api/invoices/bulk-upload` | Multi-file upload (async job) |
| `GET` | `/api/invoices/paged` | Paginated invoice list with filters |
| `GET` | `/api/invoices/{id}` | Single invoice by ID |
| `GET` | `/api/invoices/job/{job_id}` | All invoices for a job |
| `DELETE` | `/api/invoices/{id}` | Soft-delete invoice |
| `GET` | `/api/invoices/{id}/download` | Get SAS download URL |
| `GET` | `/jobs/paged` | Paginated job list |
| `GET` | `/jobs/{job_id}` | Single job by ID |
| `GET` | `/logs/db/paged` | Paginated audit logs |
| `GET` | `/logs/diagnostics/timeouts` | Timeout diagnostics |
| `GET` | `/api/dashboard/summary` | KPIs and recent activity |

## Development Commands

```bash
# Backend
cd backend
poetry run uvicorn main:app --reload         # Dev server
poetry run pytest                            # Tests
poetry run ruff check .                      # Lint
poetry run mypy .                            # Type check

# Frontend
cd frontend
npm run dev      # Dev server (http://localhost:5173)
npm run build    # Production build
npm run preview  # Preview production build
```

## Auth Flow

1. Frontend uses `@azure/msal-browser` to redirect to Microsoft login
2. On return, MSAL stores the access token in `sessionStorage`
3. Each API call attaches `Authorization: Bearer <token>` via `acquireTokenSilent`
4. Backend middleware decodes JWT payload (no signature verification — trusts corporate SSO)
5. User identity (`oid`, `email`, `name`) is extracted and attached to every invoice/log record
6. Set `SKIP_AUTH=true` or `ALLOW_DEV_AUTH=true` for local development without Entra

## Project Structure

```
/
├── backend/
│   ├── main.py                      # FastAPI app entry point
│   ├── config/database.py           # PostgreSQL connection pool + schema init
│   ├── middleware/entra_auth.py     # JWT auth middleware
│   ├── routes/
│   │   ├── auth_routes.py           # /auth/* endpoints
│   │   ├── invoice_routes.py        # /api/invoices/* endpoints
│   │   ├── jobs_routes.py           # /jobs/* endpoints
│   │   ├── logs_routes.py           # /logs/* endpoints
│   │   └── dashboard_routes.py      # /api/dashboard/* endpoints
│   ├── services/
│   │   ├── docwise_client.py        # DocWise OCR API client
│   │   ├── azure_storage_client.py  # Azure Blob Storage client
│   │   ├── jobs.py                  # Job lifecycle management
│   │   ├── logging_client.py        # Audit logging
│   │   └── file_metadata_client.py  # Invoice DB operations
│   ├── pyproject.toml
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx                  # Root app + routing
    │   ├── msalConfig.js            # MSAL configuration
    │   ├── i18n.js                  # EN/FR translations
    │   ├── context/UserContext.jsx  # Auth user state
    │   ├── components/              # Header, PrivateRoute, Notice
    │   ├── pages/                   # Upload, Bulk, Jobs, Logs, Dashboard
    │   ├── layouts/MainLayout.jsx   # App shell with nav
    │   └── services/api.js          # All API calls
    ├── package.json
    └── .env.example
```
