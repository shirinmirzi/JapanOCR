import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from middleware.entra_auth import entra_auth_middleware
from routes.auth_routes import router as auth_router
from routes.invoice_routes import router as invoice_router
from routes.jobs_routes import router as jobs_router
from routes.logs_routes import router as logs_router
from routes.dashboard_routes import router as dashboard_router
from config.database import init_database, close_connection_pool, execute_query


@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.get("/health")
async def health():
    db_ok = False
    db_error = None
    try:
        rows = execute_query("SELECT 1 AS ok")
        db_ok = bool(rows)
    except Exception as e:
        db_error = str(e)
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error: database unavailable",
    }
