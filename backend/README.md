# Invoice Processor — Backend

FastAPI backend for invoice OCR processing.

## Requirements
- Python 3.12+
- Poetry
- PostgreSQL

## Setup

```bash
poetry install
cp .env.example .env
# Edit .env with your credentials
poetry run uvicorn main:app --reload
```

## Environment Variables

| Variable | Description |
|---|---|
| POSTGRES_HOST | PostgreSQL host |
| POSTGRES_PORT | PostgreSQL port |
| POSTGRES_DB | Database name |
| POSTGRES_USER | Database user |
| POSTGRES_PASSWORD | Database password |
| POSTGRES_SCHEMA | Schema name (default: public) |
| AZURE_STORAGE_CONNECTION_STRING | Azure Blob Storage connection string |
| DOCWISE_API_KEY | DocWise API key |
| SKIP_AUTH | Set true to bypass auth (dev only) |
| ALLOW_DEV_AUTH | Allow dev-token bypass |
| CORS_ALLOWED_ORIGINS | Comma-separated allowed origins |
