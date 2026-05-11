from __future__ import annotations

from fastapi import APIRouter

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


@router.get("/api/v1/weather")
def get_cached_weather_snapshots() -> list[dict[str, object]]:
    """Return cached weather rows for coastal Christchurch suburbs (no upstream call)."""
    return list(_CACHED_SNAPSHOTS)
