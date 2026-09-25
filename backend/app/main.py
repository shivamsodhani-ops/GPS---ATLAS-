from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, engine
from .routers import admin, auth, departments, documents, search, users
from .seed import run_seed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("atlas")

app = FastAPI(
    title=settings.app_name,
    description="Information Intelligence & Document Protection Platform for GPS Renewables",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    run_seed()
    from .services import embeddings

    logger.info("GPS ATLAS started. Embedding backend: %s", embeddings.backend_name())


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(departments.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    from .services import embeddings

    return {"status": "ok", "app": settings.app_name, "embedding_backend": embeddings.backend_name()}


# --- serve the built React app (single-process deployment) -----------------
_frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
