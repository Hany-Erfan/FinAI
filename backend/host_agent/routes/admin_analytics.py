"""Admin-only endpoint that queries Loki for dashboard analytics."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

import httpx

from backend.bank_server.utils.security_deps import require_admin
from observability import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Analytics"])

LOKI_URL = os.getenv("LOKI_URL", "http://lgtm:3100")

# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class TimeSeriesPoint(BaseModel):
    timestamp: str
    value: float


class LanguageCount(BaseModel):
    language: str
    count: int


class AnalyticsResponse(BaseModel):
    total_sessions: int
    total_sessions_series: list[TimeSeriesPoint]
    containment_rate: float
    escalated_count: int
    avg_response_time: float | None
    response_time_series: list[TimeSeriesPoint]
    language_distribution: list[LanguageCount]


# ---------------------------------------------------------------------------
# Loki helpers
# ---------------------------------------------------------------------------

_LANGUAGE_MAP = {
    "Language.EN": "English",
    "language.EN": "English",
    "Language.AR": "Arabic",
    "language.AR": "Arabic",
}


def _calc_step(start: datetime, end: datetime) -> str:
    """Pick a sensible step size so Loki returns ~60-120 data-points."""
    delta_s = int((end - start).total_seconds())
    if delta_s <= 3600:
        return "60s"
    if delta_s <= 86400:
        return "300s"
    if delta_s <= 604800:
        return "1800s"
    return "3600s"


def _range_str(start: datetime, end: datetime) -> str:
    """Full range duration string for instant queries (e.g. '21600s')."""
    return f"{int((end - start).total_seconds())}s"


async def _query_range(client: httpx.AsyncClient, expr: str, start: datetime, end: datetime, step: str):
    """Run a Loki range query and return the raw JSON result."""
    resp = await client.get(
        f"{LOKI_URL}/loki/api/v1/query_range",
        params={
            "query": expr,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "step": step,
        },
    )
    resp.raise_for_status()
    return resp.json()


async def _query_instant(client: httpx.AsyncClient, expr: str, time: datetime):
    """Run a Loki instant query and return the raw JSON result."""
    resp = await client.get(
        f"{LOKI_URL}/loki/api/v1/query",
        params={
            "query": expr,
            "time": time.isoformat(),
        },
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Individual metric fetchers (each returns defaults on failure)
# ---------------------------------------------------------------------------

async def _fetch_total_sessions(client: httpx.AsyncClient, start: datetime, end: datetime, step: str):
    try:
        expr = f'sum(count_over_time({{service_name="host-agent"}} |= "has started" [{step}]))'
        data = await _query_range(client, expr, start, end, step)
        series: list[TimeSeriesPoint] = []
        total = 0
        for result in data.get("data", {}).get("result", []):
            for ts, val in result.get("values", []):
                v = float(val)
                total += int(v)
                series.append(TimeSeriesPoint(timestamp=str(ts), value=v))
        return total, series
    except Exception as exc:
        logger.warning(f"Failed to fetch total sessions from Loki: {exc}")
        return 0, []


async def _fetch_escalations(client: httpx.AsyncClient, start: datetime, end: datetime, range_str: str):
    try:
        expr = f'sum(count_over_time({{service_name="host-agent"}} |= "Agent escalated for session" [{range_str}]))'
        data = await _query_instant(client, expr, end)
        for result in data.get("data", {}).get("result", []):
            val = result.get("value", [None, "0"])
            return int(float(val[1]))
        return 0
    except Exception as exc:
        logger.warning(f"Failed to fetch escalations from Loki: {exc}")
        return 0


async def _fetch_response_time(client: httpx.AsyncClient, start: datetime, end: datetime, step: str):
    try:
        expr = (
            'avg(avg_over_time({service_name="host-agent"} |= "Response time" '
            '| regexp "Response time for session .*: (?P<duration>[0-9.]+)s" '
            f'| unwrap duration [{step}]))'
        )
        data = await _query_range(client, expr, start, end, step)
        series: list[TimeSeriesPoint] = []
        latest: float | None = None
        for result in data.get("data", {}).get("result", []):
            for ts, val in result.get("values", []):
                v = float(val)
                series.append(TimeSeriesPoint(timestamp=str(ts), value=round(v, 2)))
                latest = round(v, 2)
        return latest, series
    except Exception as exc:
        logger.warning(f"Failed to fetch response time from Loki: {exc}")
        return None, []


async def _fetch_language_distribution(client: httpx.AsyncClient, start: datetime, end: datetime, range_str: str):
    try:
        expr = (
            'sum by (language) (count_over_time({service_name="host-agent"} '
            '|= "Language for session" '
            '| regexp "Language for session .*: (?P<language>.*)" '
            f'[{range_str}]))'
        )
        data = await _query_instant(client, expr, end)
        counts: list[LanguageCount] = []
        for result in data.get("data", {}).get("result", []):
            raw_label = result.get("metric", {}).get("language", "Unknown")
            label = _LANGUAGE_MAP.get(raw_label, raw_label)
            val = result.get("value", [None, "0"])
            counts.append(LanguageCount(language=label, count=int(float(val[1]))))
        return counts
    except Exception as exc:
        logger.warning(f"Failed to fetch language distribution from Loki: {exc}")
        return []


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

def _default_start() -> str:
    """ISO string for 6 hours ago."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()


def _default_end() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    start: str = Query(default_factory=_default_start),
    end: str = Query(default_factory=_default_end),
    _admin=Depends(require_admin),
):
    """Return aggregated analytics sourced from Loki logs."""
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {exc}") from exc

    step = _calc_step(start_dt, end_dt)
    range_str = _range_str(start_dt, end_dt)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            (total, sessions_series), escalated, (avg_rt, rt_series), lang_dist = await asyncio.gather(
                _fetch_total_sessions(client, start_dt, end_dt, step),
                _fetch_escalations(client, start_dt, end_dt, range_str),
                _fetch_response_time(client, start_dt, end_dt, step),
                _fetch_language_distribution(client, start_dt, end_dt, range_str),
            )
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Loki service is unreachable",
        ) from exc

    containment = 0.0
    if total > 0:
        containment = round((1 - escalated / total) * 100, 1)

    return AnalyticsResponse(
        total_sessions=total,
        total_sessions_series=sessions_series,
        containment_rate=containment,
        escalated_count=escalated,
        avg_response_time=avg_rt,
        response_time_series=rt_series,
        language_distribution=lang_dist,
    )
