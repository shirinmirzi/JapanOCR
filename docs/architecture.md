# System Architecture

## Overview

Japan OCR Tool is an OCR-powered invoice data-extraction platform built on:

- **Backend**: Python / FastAPI
- **Frontend**: React (Vite + Tailwind CSS)
- **OCR Engine**: DocWise API
- **Storage**: Azure Blob Storage (local filesystem fallback for development)
- **Auth**: Microsoft Azure Entra ID (MSAL)
- **Database**: PostgreSQL

---

## Component Diagram

```
Browser (React SPA)
      │  HTTPS + Bearer JWT
      ▼
FastAPI Backend
  ├── Entra Auth Middleware  (JWT validation on every request)
  ├── /api/invoices/*        (upload, query, delete)
  ├── /api/config/*          (master data upload/retrieval)
  ├── /jobs/*                (bulk job status)
  ├── /logs/*                (processing log queries)
  └── /api/dashboard/*       (KPI aggregates)
      │
      ├── DocWise API        (external OCR service)
      ├── Azure Blob Storage (file persistence)
      └── PostgreSQL DB      (invoice, job, log records)
```

---

## Data Flow – Single Invoice Upload

1. User selects a PDF and invoice type (daily / monthly) on the Upload page.
2. React sends a `POST /api/invoices/upload` multipart request with a Bearer JWT.
3. Entra auth middleware validates the JWT and populates `request.state.user`.
4. `invoice_routes.upload_invoice` writes a temporary file, calls DocWise, and parses
   the structured text response into invoice fields.
5. The renamed PDF is uploaded to Azure Blob Storage under an execution-folder path.
6. An invoice record is inserted into PostgreSQL; a log entry records the outcome.
7. The extracted fields and storage metadata are returned to the browser.

## Data Flow – Bulk Invoice Upload

1. User selects multiple PDFs and clicks **Upload**.
2. React sends `POST /api/invoices/bulk-upload`; the backend creates a job record
   (status: `queued`) and starts a background thread.
3. The route returns a `job_id` immediately so the browser can poll for progress.
4. The background thread processes each file sequentially, updating
   `processed_count` and `results` in the job row after each file.
5. The React Upload page polls `GET /jobs/<job_id>` every two seconds and updates
   the per-file status table in real time.
6. The job reaches a terminal state: `done`, `partial`, or `failed`.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Background thread for bulk upload | Keeps the HTTP response latency low; FastAPI's `BackgroundTasks` runs in the same process, avoiding worker-spawn overhead for small batches. |
| Two-phase logging | `log_processing_start` captures the file at intake; `update_log_entry` records the outcome. This ensures every file has a terminal log state even if an exception escapes. |
| Soft delete for invoices | Preserves audit trails; invoice records are flagged `deleted` rather than physically removed. |
| DoNotSend routing | Non-numeric `destination_cd` values in the master table route the PDF to a quarantine folder instead of a customer destination. The count of routed-away invoices is surfaced on the Dashboard as a dedicated amber KPI banner and as an output-folder badge (`🚫 DoNotSend`) in the Recent Invoices table. |
| Local storage fallback | When no Azure connection string is set, files are written to `backend/storage_pdf/`. This makes local development work without cloud credentials. |

---

## Database Schema

### `jobs`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | UUID generated at job creation |
| `created_at` | TIMESTAMPTZ | Auto-set on insert |
| `user_id` | TEXT | Username of the submitting user |
| `status` | TEXT | queued → processing → done / partial / failed |
| `total_count` | INTEGER | Number of files in the batch |
| `processed_count` | INTEGER | Incremented after each file completes |
| `filenames` | JSONB | Array of original filenames |
| `results` | JSONB | Per-file result snapshots |
| `batch_name` | TEXT | Optional human-readable batch label |

### `invoices`

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `job_id` | TEXT FK → jobs | Null for single uploads |
| `filename` | TEXT | Original filename |
| `invoice_number` | TEXT | Extracted by OCR |
| `vendor_name` | TEXT | Extracted by OCR |
| `customer_code` | TEXT | Extracted by OCR |
| `invoice_date` | TEXT | YYYY/MM/DD from OCR |
| `blob_url` | TEXT | Azure URL or local URI |
| `blob_path` | TEXT | Relative path used for SAS generation |
| `upload_folder` | TEXT | Logical folder path for UI display |
| `status` | TEXT | processed / error / deleted |
| `line_items` | JSONB | Array of line item dicts |

### `logs`

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `timestamp` | TIMESTAMPTZ | Auto-set on insert |
| `filename` | TEXT | Original filename |
| `status` | TEXT | processing → success / error / timeout |
| `message` | TEXT | Human-readable success message |
| `error` | TEXT | Error detail on failure |
| `metadata` | JSONB | renamed_filename, folder_name, execution_folder, module |
| `user_id` | TEXT | Submitting user |

### `daily_invoice_master` / `monthly_invoice_master`

| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `customer_cd` | TEXT | Customer code from the invoice |
| `destination_cd` | TEXT | Numeric folder code or DoNotSend keyword |
| `row_number` | INTEGER | Original row number from the uploaded file |

---

Author: SHIRIN MIRZI M K
