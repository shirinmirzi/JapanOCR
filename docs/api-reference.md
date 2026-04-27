# REST API Reference

All endpoints (except `/health` and OpenAPI docs) require an `Authorization: Bearer <token>` header.
Set `SKIP_AUTH=true` in `backend/.env` to bypass this during local development.

Base URL: `http://localhost:8000` (development)

---

## Authentication

### `GET /auth/me`

Returns the authenticated user's profile.

**Response**

```json
{
  "username": "user@corp.com",
  "name": "Jane Doe",
  "oid": "azure-oid",
  "email": "user@corp.com",
  "initials": "JD"
}
```

### `POST /auth/verify-token`

Validates a raw JWT and returns decoded user info.

**Request body**

```json
{ "token": "<jwt-string>" }
```

**Response**

```json
{ "valid": true, "user": { "username": "...", "name": "...", ... } }
```

### `GET /auth/logout`

Stateless logout acknowledgement for SPA clients.

**Response**

```json
{ "logged_out": true }
```

---

## Health

### `GET /health`

Lightweight liveness and database reachability probe.

**Response**

```json
{ "status": "ok", "database": "connected" }
```

Status is `"degraded"` and `database` contains an error string when the DB is unreachable.

---

## Invoices

### `POST /api/invoices/upload`

Process a single PDF invoice synchronously.

**Form fields**

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | ✓ | PDF invoice to process |
| `invoice_type` | string | — | `"daily"` (default) or `"monthly"` |

**Response** – extracted invoice fields plus storage metadata.

### `POST /api/invoices/bulk-upload`

Queue multiple PDFs for background OCR processing.

**Form fields**

| Field | Type | Required | Description |
|---|---|---|---|
| `files` | File[] | ✓ | One or more PDF invoices |
| `invoice_type` | string | — | `"daily"` (default) or `"monthly"` |

**Response**

```json
{
  "job_id": "uuid",
  "accepted": 3,
  "filenames": ["a.pdf", "b.pdf", "c.pdf"],
  "execution_folder": "20250430_143022"
}
```

### `GET /api/invoices/paged`

Return a paginated, filterable list of invoices.

**Query parameters**

| Param | Default | Description |
|---|---|---|
| `page` | 1 | 1-based page number |
| `page_size` | 20 | Max records per page (1–100) |
| `q` | — | Free-text search across vendor, invoice number, filename |
| `status` | — | Exact status filter |
| `since` | — | ISO timestamp lower bound |
| `until` | — | ISO timestamp upper bound |
| `sort_by` | `created_at` | Column to sort by |
| `sort_dir` | `desc` | `asc` or `desc` |

**Response** – `{ items, total, page, page_size, total_pages }`

### `GET /api/invoices/{invoice_id}`

Return a single invoice record by its primary key.

### `GET /api/invoices/{invoice_id}/download`

Generate a time-limited SAS download URL for the stored invoice PDF.

**Response** – `{ "download_url": "https://..." }`

### `GET /api/invoices/job/{job_id}`

Return all invoice records associated with a bulk-upload job.

### `DELETE /api/invoices/{invoice_id}`

Soft-delete an invoice (sets status to `"deleted"`).

**Response** – `{ "deleted": true, "id": 42 }`

---

## Jobs

### `GET /jobs/paged`

Return a paginated list of bulk-upload jobs.

**Query parameters** – `page`, `page_size`, `sort_by`, `sort_dir`, `status`, `user_id`

**Response** – `{ items, total, page, page_size, total_pages }`

### `GET /jobs/{job_id}`

Return a single job record by its UUID.

**Response** – job dict including `status`, `processed_count`, `total_count`, and `results`.

---

## Logs

### `GET /logs/db/paged`

Return a paginated, filtered list of processing log entries.

**Query parameters**

| Param | Description |
|---|---|
| `page`, `page_size` | Pagination |
| `status` | Exact status filter |
| `statuses` | Comma-separated list of statuses (SQL IN) |
| `q` | Free-text search across filename, message, metadata |
| `since`, `until` | ISO timestamp bounds |
| `sort_by`, `sort_dir` | Sorting |
| `user_id` | Filter to one user |
| `module` | Pipeline module tag (`invoice`, etc.) |

**Response** – `{ items, total, page, page_size, total_pages }` where each item includes
flattened `renamed_filename`, `folder_name`, and `execution_folder` from JSONB metadata.

### `GET /logs/diagnostics/timeouts`

Return aggregated status counts from the logs table.

**Response**

```json
{
  "timeout_count": 0,
  "error_count": 2,
  "success_count": 45,
  "total": 47,
  "last_entry": "2025-04-30T14:30:00+00:00"
}
```

---

## Dashboard

### `GET /api/dashboard/summary`

Aggregate KPI metrics and recent-activity data.

**Query parameters** – `jobs_limit` (1–50), `invoices_limit` (1–50),
`failures_limit` (1–50), `since` (ISO timestamp)

**Response**

```json
{
  "kpis": {
    "invoices_total": 120,
    "jobs_total": 15,
    "logs_total": 240,
    "by_status": { "processed": 110, "error": 10 },
    "vendors": [{ "vendor_name": "Acme", "count": 30 }]
  },
  "recent": {
    "jobs": [...],
    "invoices": [...],
    "failures": [...]
  }
}
```

---

## Config / Master Data

### `POST /api/config/master-upload`

Bulk-upload a master data file (.xlsx, .xlsm, or .csv) that maps customer codes
to destination codes.

**Form fields**

| Field | Type | Required | Description |
|---|---|---|---|
| `master_type` | string | ✓ | `"daily"` or `"monthly"` |
| `file` | File | ✓ | Excel or CSV master data file |

**Response**

```json
{
  "master_type": "daily",
  "filename": "master.csv",
  "inserted": 98,
  "skipped": 2,
  "invalid_rows": [{ "row": 5, "reason": "customer_cd is empty", "data": {...} }]
}
```

### `GET /api/config/master-data/{master_type}`

Return current master data rows for `daily` or `monthly`.

**Response** – `{ master_type, count, rows: [...] }`

---

Author: SHIRIN MIRZI M K
