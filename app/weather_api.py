from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter

from app.nz_time import nz_today

router = APIRouter(tags=["weather"])

# Cached WeatherSnapshot-style rows for Redcliffs and nearby Christchurch suburbs (demo).
_CACHED_SNAPSHOTS: list[dict[str, object]] = [
    {
        "weather_snapshot_id": 101,
        "suburb": "Redcliffs",
        "temperature": 16.2,
        "humidity": 72.0,
        "wind_speed": 18.0,
        "description": "Fresh nor-west breeze; outdoor work feasible with basic precautions.",
        "timestamp": "2025-06-01T08:00:00+00:00",
    },
    {
        "weather_snapshot_id": 102,
        "suburb": "Christchurch CBD",
        "temperature": 14.5,
        "humidity": 78.0,
        "wind_speed": 10.0,
        "description": "Light drizzle clearing mid-morning.",
        "timestamp": "2025-06-01T08:05:00+00:00",
    },
    {
        "weather_snapshot_id": 103,
        "suburb": "Sumner",
        "temperature": 15.0,
        "humidity": 80.0,
        "wind_speed": 22.0,
        "description": "Onshore chop; delay exposed scaffold work.",
        "timestamp": "2025-06-01T08:10:00+00:00",
    },
]

# Rotating demo labels for a 14-day outlook (planning aid; not a live MET feed).
_FORECAST_PATTERN: list[tuple[str, int, int, int]] = [
    ("Fine & dry", 18, 9, 8),
    ("Partly cloudy", 16, 11, 15),
    ("Morning showers clearing", 15, 10, 40),
    ("Light winds, high cloud", 17, 12, 5),
    ("Brief rain periods", 14, 9, 55),
    ("Cool southerly change", 13, 8, 25),
    ("Mild nor-wester", 19, 11, 10),
]


def _forecast_14d() -> list[dict[str, object]]:
    start = nz_today()
    out: list[dict[str, object]] = []
    for i in range(14):
        d = start + timedelta(days=i)
        label, hi, lo, pop = _FORECAST_PATTERN[i % len(_FORECAST_PATTERN)]
        wind = 10.0 + (i % 5) * 3.5
        out.append(
            {
                "date": d.isoformat(),
                "weekday": d.strftime("%a"),
                "label": label,
                "high_c": hi + (i % 3) - 1,
                "low_c": lo,
                "precipitation_probability": pop,
                "wind_kmh": round(wind, 1),
            }
        )
    return out


def _chip_summary(snaps: list[dict[str, object]]) -> str:
    if not snaps:
        return "Conditions look workable for outdoor visits."
    desc = str(snaps[0].get("description") or "").strip()
    if not desc:
        return "Christchurch area — check the forecast for details."
    if len(desc) > 72:
        return desc[:69] + "…"
    return desc


@router.get("/api/v1/weather")
def get_weather() -> dict[str, object]:
    """Demo weather: suburb snapshots plus a 14-day outlook (Pacific/Auckland calendar)."""
    snaps = list(_CACHED_SNAPSHOTS)
    return {
        "summary": _chip_summary(snaps),
        "region": "Christchurch area",
        "timezone": "Pacific/Auckland",
        "snapshots": snaps,
        "forecast": _forecast_14d(),
    }
