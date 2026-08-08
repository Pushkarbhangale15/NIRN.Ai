"""
app.py — NIRN.Ai backend entry point.

Run it from INSIDE the backend/ folder:

    cd backend
    uvicorn app:app --reload

Then open http://localhost:8000/docs — FastAPI generates an interactive
page from the schemas where every endpoint can be called from the
browser. Send that link to the frontend developer; it is the complete
API contract, live and always in sync with the code.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

import llm
import retrieval
from admin_routes import router as admin_router
from auth_routes import router as auth_router
from config import settings
from export_docx import router as export_router
from export_pdf_lock import router as export_pdf_lock_router
from knowledge import get_knowledge_service
from rate_limit import limiter
from routes import router
from schemas import HealthResponse
from workflow_routes import router as workflow_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
)
logger = logging.getLogger(settings.APP_NAME)

# Load Knowledge Base singleton on app startup
try:
    _ks = get_knowledge_service()
    _ks_stats = _ks.get_summary_stats()
    logger.info(
        "Government Knowledge Base initialized | %d terms, %d departments, %d designations",
        _ks_stats["total_terms"], _ks_stats["total_departments"], _ks_stats["total_designations"]
    )
except Exception as _exc:
    logger.error("Failed to load Knowledge Base: %s", _exc)

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version=settings.VERSION,
    description=(
        "AI-assisted Government Resolution drafting and alignment for the "
        "Higher and Technical Education Department, Government of Maharashtra."
    ),
)

# Without this, the browser silently blocks every request coming from
# the React dev server, because it runs on a different port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# slowapi rate limiting — currently only /api/auth/login opts in
# (5/minute per IP, see auth_routes.py), guarding against credential
# brute-forcing.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(export_router)
app.include_router(export_pdf_lock_router)
app.include_router(workflow_router)

@app.get("/", tags=["health"])
def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """
    What is alive, and what is still stubbed.

    The two booleans are a live progress bar for the team: both are
    False on Day 1 and both should be True by the end of Day 2.
    """
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version=settings.VERSION,
        vector_db_connected=retrieval.is_connected(),
        llm_configured=llm.is_configured(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all so a judge never sees a raw Python stack trace during the
    demo. The full trace still goes to your terminal.
    """
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal error. Check server logs."},
    )


logger.info("%s v%s | vector DB: %s | LLM: %s | KB Terms: %d",
            settings.APP_NAME, settings.VERSION,
            retrieval.is_connected(), llm.is_configured(),
            get_knowledge_service().get_summary_stats().get("total_terms", 0))

