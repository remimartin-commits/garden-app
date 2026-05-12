from __future__ import annotations

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.auth import SESSION_USER_SESSION_KEY, verify_owner_credentials
from app.auth_gate import AuthGateMiddleware
from app.customer_api import router as customer_router
from app.property_api import router as property_router
from app.jobs_api import router as jobs_router
from app.schedule_api import router as schedule_router
from app.quotes_api import router as quotes_router
from app.invoices_api import router as invoices_router
from app.settings_api import ensure_default_settings, router as settings_router
from app.weather_api import router as weather_router
from app.service_templates_api import router as service_templates_router
from app.audit_api import router as audit_router
from app.recurring_jobs_api import router as recurring_jobs_router
from app.reporting_api import router as reporting_router
from app.plant_exchange_api import router as plant_exchange_router
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.entities import DashboardMetrics
from app.database import (
    SessionLocal,
    apply_sqlite_migrations,
    engine,
    Base,
    ensure_demo_invoice_if_empty,
    seed_database_if_empty,
    get_db,
)
from app.models import Job as JobORM
from app.nz_time import nz_calendar_date_from_stored, nz_today

_APP_INDEX = Path(__file__).resolve().parent / "static" / "index.html"
_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _safe_next_path(raw: str) -> str:
    s = (raw or "").strip()
    if not s.startswith("/") or s.startswith("//"):
        return "/"
    return s


def _workflow_cancelled(status: str | None) -> bool:
    s = (status or "").strip().lower()
    return s in ("cancelled", "canceled")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_database_if_empty(db)
        ensure_default_settings(db)
        # ensure_demo_invoice_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="GreenOps — Gardening Business Manager",
    description="Field service management APIs for gardening businesses.",
)

try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except RuntimeError:
    pass

app.include_router(customer_router)
app.include_router(property_router)
app.include_router(jobs_router)
app.include_router(schedule_router)
app.include_router(quotes_router)
app.include_router(invoices_router)
app.include_router(settings_router)
app.include_router(weather_router)
app.include_router(service_templates_router)
app.include_router(audit_router)
app.include_router(recurring_jobs_router)
app.include_router(reporting_router)
app.include_router(plant_exchange_router)

app.add_middleware(AuthGateMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    session_cookie="session",
    max_age=14 * 24 * 60 * 60,
    same_site="lax",
    https_only=config.SESSION_COOKIE_SECURE,
)

Base.metadata.create_all(bind=engine)
apply_sqlite_migrations(engine)
_startup_db = SessionLocal()
try:
    seed_database_if_empty(_startup_db)
    ensure_default_settings(_startup_db)
    # ensure_demo_invoice_if_empty(_startup_db)
finally:
    _startup_db.close()


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> RedirectResponse:
    return RedirectResponse(url="/static/favicon.svg", status_code=307)


@app.get("/login", response_model=None, include_in_schema=False)
async def login_page(
    request: Request,
    redirect_after: str = Query("", alias="next"),
):
    if not config.auth_gate_enabled():
        return RedirectResponse("/", status_code=302)
    if request.session.get(SESSION_USER_SESSION_KEY):
        return RedirectResponse(_safe_next_path(redirect_after), status_code=302)
    return _TEMPLATES.TemplateResponse(
        request,
        "login.html",
        {"error": None, "next": redirect_after or ""},
    )


@app.post("/login", response_model=None, include_in_schema=False)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_path: str = Form("", alias="next"),
):
    if not config.auth_gate_enabled():
        return RedirectResponse("/", status_code=302)
    if not verify_owner_credentials(username, password):
        return _TEMPLATES.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Invalid username or password.",
                "next": (next_path or "").strip(),
            },
            status_code=401,
        )
    request.session[SESSION_USER_SESSION_KEY] = username.strip()
    return RedirectResponse(_safe_next_path(next_path), status_code=302)


@app.post("/logout", include_in_schema=False)
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root() -> str:
    try:
        return _APP_INDEX.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "<h1>GreenOps</h1><p>Missing app/static/index.html</p>"


@app.get("/api/v1/dashboard", response_model=DashboardMetrics)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardMetrics:
    today = nz_today()
    jobs_today = 0
    for row in db.scalars(select(JobORM).where(JobORM.scheduled_date.isnot(None))).all():
        if _workflow_cancelled(row.workflow_status):
            continue
        if nz_calendar_date_from_stored(row.scheduled_date) == today:
            jobs_today += 1
    return DashboardMetrics(jobs_scheduled_today=jobs_today)
