from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.schemas import HealthResponse, StatusResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@router.get("/status", response_model=StatusResponse)
async def status(request: Request):
    bm = request.app.state.browser_manager
    return StatusResponse(
        status="ok" if bm.is_ready else "starting",
        sessions_active=bm.active_session_count,
        sessions_max=bm._config.max_sessions,
        uptime_seconds=bm.uptime_seconds,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
