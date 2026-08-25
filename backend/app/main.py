import os
from datetime import datetime, timezone
from hmac import compare_digest

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, text

from app.config import get_settings
from app.db import SessionLocal, engine
from app.inference import InferenceError, asi_cloud_from_environment
from app.models import User
from app.routes.investigations import router as investigations_router
from app.routes.literature import router as literature_router
from app.routes.knowledge import router as knowledge_router
from app.queue import get_redis_connection
from app.schemas import OAuthUserSync, UserProfileUpdate, UserRead
from app.security import get_current_user, require_admin

settings = get_settings()

app = FastAPI(
    title="HelixMind API",
    version="0.1.0",
    description="Scientific intelligence API for evidence-led CRISPR research.",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
app.include_router(investigations_router)
app.include_router(literature_router)
app.include_router(knowledge_router)


class HealthResponse(BaseModel):
    status: str
    service: str


@app.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Local readiness probe. The API remains private until reverse-proxied later."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return HealthResponse(status="ok", service="helixmind-api")


@app.post("/api/v1/auth/sync", response_model=UserRead, tags=["authentication"])
def sync_oauth_user(
    payload: OAuthUserSync,
    x_helixmind_auth_sync: str | None = Header(default=None),
) -> UserRead:
    """Persist a Google identity after NextAuth has completed provider verification."""
    if not settings.auth_sync_secret or not x_helixmind_auth_sync or not compare_digest(
        x_helixmind_auth_sync, settings.auth_sync_secret
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid identity sync request.")

    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="A valid email address is required.")

    google_name = " ".join(payload.name.split()) if payload.name and payload.name.strip() else None
    is_configured_admin = email == settings.admin_email.strip().lower()

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=google_name, role="ADMIN" if is_configured_admin else "USER")
            session.add(user)
        else:
            # Google provides the initial display name; a user-edited name remains authoritative afterward.
            user.email = email
            if not user.name or not user.name.strip():
                user.name = google_name
            if is_configured_admin:
                user.role = "ADMIN"
        user.image = payload.image
        user.provider_account_id = payload.provider_account_id or user.provider_account_id
        user.last_login_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(user)
        return UserRead.model_validate(user, from_attributes=True)


@app.get("/api/v1/me", response_model=UserRead, tags=["authentication"])
def current_user(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user, from_attributes=True)


@app.patch("/api/v1/me", response_model=UserRead, tags=["authentication"])
def update_current_user(payload: UserProfileUpdate, user: User = Depends(get_current_user)) -> UserRead:
    with SessionLocal() as session:
        stored_user = session.get(User, user.id)
        if stored_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found.")
        stored_user.name = payload.display_name
        session.commit()
        session.refresh(stored_user)
        return UserRead.model_validate(stored_user, from_attributes=True)


@app.get("/api/v1/admin/diagnostics", tags=["administration"])
def admin_diagnostics(_: User = Depends(require_admin)) -> dict:
    """Return redacted operational status only; never return environment values."""
    redis_ok = False
    try:
        redis_ok = bool(get_redis_connection().ping())
    except Exception:
        redis_ok = False
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    inference = {"provider": "asi", "configured": False, "reachable": False, "models": [], "selected_chat_model": os.getenv("ASI_CLOUD_CHAT_MODEL", "asi1-mini"), "selected_embedding_model": os.getenv("ASI_CLOUD_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")}
    try:
        asi = asi_cloud_from_environment()
        inference["configured"] = bool(asi.api_keys)
        inference["models"] = asi.discover_models()
        inference["reachable"] = True
    except InferenceError as error:
        inference["error_category"] = error.category
    except Exception:
        inference["error_category"] = "provider_failure"
    finally:
        if "asi" in locals():
            asi.close()
    return {
        "api": "ok",
        "postgresql": "ok",
        "redis": "ok" if redis_ok else "unavailable",
        "omegaclaw": "configured-runtime",
        "llm_providers": {
            "configured_order": [item.strip() for item in os.getenv("OMEGACLAW_PROVIDER_ORDER", "gemini,groq").split(",") if item.strip()],
            "selected": os.getenv("OMEGACLAW_PROVIDER", "gemini"),
            "gemini": "configured" if os.getenv("GEMINI_API_KEY") else "not-configured",
            "groq": "configured" if os.getenv("GROQ_API_KEY") else "not-configured",
            "asi": inference,
        },
    }
