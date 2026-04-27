"""
Japan OCR Tool - Application Entry Point

Bootstraps the FastAPI application: configures logging, initialises the
database connection pool on startup, registers CORS and authentication
middleware, and mounts all API routers.

Key Features:
- Lifespan management: database init on startup, pool teardown on shutdown
- CORS: origins controlled via CORS_ALLOWED_ORIGINS environment variable
- Auth: Azure Entra ID JWT middleware applied globally to all HTTP routes
- Health endpoint: lightweight liveness/readiness probe at GET /health

Dependencies: FastAPI, psycopg2, python-dotenv, Azure SDK
Author: SHIRIN MIRZI M K
"""

from dotenv import load_dotenv
load_dotenv()

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.database import close_connection_pool, execute_query, init_database
from middleware.entra_auth import entra_auth_middleware
from routes.auth_routes import router as auth_router
from routes.config_routes import router as config_router
from routes.dashboard_routes import router as dashboard_router
from routes.invoice_routes import router as invoice_router
from routes.jobs_routes import router as jobs_router
from routes.logs_routes import router as logs_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown events.

    Args:
        app: The FastAPI application instance provided by the framework.

    Raises:
        Exception: Startup database errors are logged but do not abort launch,
            allowing the process to start in a degraded state.
    """
    try:
        init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
    yield
    close_connection_pool()
    logger.info("Connection pool closed")


app = FastAPI(
    title="Invoice Processor API",
    version="0.1.0",
    description="OCR-powered invoice data extraction using DocWise, FastAPI, and Azure",
    lifespan=lifespan,
)

cors_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(entra_auth_middleware)

app.include_router(auth_router)
app.include_router(invoice_router)
app.include_router(jobs_router)
app.include_router(logs_router)
app.include_router(dashboard_router)
app.include_router(config_router)


@app.get("/health")
async def health():
    """
    Report application liveness and database reachability.

    Returns:
        Dict with 'status' ("ok" or "degraded") and 'database'
        ("connected" or an error string describing the failure).
    """
    db_ok = False
    try:
        rows = execute_query("SELECT 1 AS ok")
        db_ok = bool(rows)
    except Exception as e:
        logger.warning("Health check database query failed: %s", e)
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error: database unavailable",
    }
