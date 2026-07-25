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

import llm
import retrieval
from config import settings
from routes import router
from schemas import HealthResponse

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
)
logger = logging.getLogger(settings.APP_NAME)

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

app.include_router(router)

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


logger.info("%s v%s | vector DB: %s | LLM: %s",
            settings.APP_NAME, settings.VERSION,
            retrieval.is_connected(), llm.is_configured())
