from __future__ import annotations

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.customer_api import router as customer_router
from app.property_api import router as property_router
from app.jobs_api import router as jobs_router
from app.schedule_api import router as schedule_router
from app.quotes_api import router as quotes_router
from app.invoices_api import router as invoices_router
from app.settings_api import router as settings_router
from app.weather_api import router as weather_router
from app.service_templates_api import router as service_templates_router
from app.audit_api import router as audit_router
from app.recurring_job_api import router as recurring_job_router
from app.recurring_jobs_api import router as recurring_jobs_router
from app.reporting_api import router as reporting_router
from app.entities import DashboardMetrics

_APP_INDEX = Path(__file__).resolve().parent / "static" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
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
app.include_router(recurring_job_router)
app.include_router(recurring_jobs_router)
app.include_router(reporting_router)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> RedirectResponse:
    return RedirectResponse(url="/static/favicon.svg", status_code=307)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root() -> str:
    try:
        return _APP_INDEX.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "<h1>GreenOps</h1><p>Missing app/static/index.html</p>"


@app.get("/api/v1/dashboard", response_model=DashboardMetrics)
def get_dashboard() -> DashboardMetrics:
    return DashboardMetrics()
