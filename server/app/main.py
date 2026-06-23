"""Punkt wejścia FastAPI — VCA License/Admin API (Faza A)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers import license as license_router
from .routers import downloads as downloads_router
from .routers import admin as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MVP: tworzymy tabele przy starcie. Migracje (Alembic) dołożymy później.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Vibe Coding Assistant — License/Admin API", version="0.1.0", lifespan=lifespan)

_origins = ["*"] if settings.cors_origins.strip() == "*" \
    else [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Panel uwierzytelnia się tokenem Bearer (nie ciasteczkami), więc credentials
    # wyłączone — dzięki temu allow_origins="*" działa poprawnie w przeglądarce.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "vca-api", "version": app.version}


app.include_router(license_router.router, prefix="/api/license", tags=["license"])
app.include_router(downloads_router.router, prefix="/api/downloads", tags=["downloads"])
app.include_router(admin_router.router, prefix="/api/admin", tags=["admin"])
