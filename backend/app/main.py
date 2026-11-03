import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import db
from app.routes import pull, push
from app.services import companies, refresh, snapshot

log = logging.getLogger("finn")


def _scheduler(every_min: int) -> None:
    """Periodic refresh for hosts that stay awake. Off unless AUTO_REFRESH_MINUTES is set."""
    while True:
        time.sleep(every_min * 60)
        try:
            refresh.run(days=3)
        except Exception as e:
            log.warning("Scheduled refresh failed: %s", e)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.connect()
    loaded = snapshot.load_if_empty()
    if loaded:
        log.info("Booted from seed snapshot: %s", loaded)
    companies.seed_defaults()
    if settings.auto_refresh_minutes > 0:
        threading.Thread(target=_scheduler, args=(settings.auto_refresh_minutes,), daemon=True).start()
    yield


app = FastAPI(title="FINN API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(push.router)
app.include_router(pull.router)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "llm_configured": bool(settings.anthropic_api_key) and settings.llm_enabled,
        "companies": db.query_one("SELECT COUNT(*) n FROM companies")["n"],
        "snapshot": db.kv_get("snapshot_loaded"),
        "auto_refresh_minutes": settings.auto_refresh_minutes,
    }
