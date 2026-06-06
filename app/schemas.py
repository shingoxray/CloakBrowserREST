from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WaitUntil(str, Enum):
    LOAD = "load"
    DOMCONTENTLOADED = "domcontentloaded"
    NETWORKIDLE = "networkidle"
    COMMIT = "commit"


class FetchOptions(BaseModel):
    proxy: Optional[str] = Field(None, description="Proxy URL (e.g. http://user:pass@host:port)")
    geoip: bool = Field(False, description="Auto-detect timezone/locale from proxy IP")
    humanize: bool = Field(False, description="Enable human-like mouse/keyboard/scroll behavior")
    headless: bool = Field(False, description="Run browser headless (no Xvfb display)")
    timeout_ms: int = Field(60000, description="Navigation timeout in milliseconds", ge=1000, le=120000)
    wait_until: WaitUntil = Field(WaitUntil.NETWORKIDLE, description="Playwright waitUntil strategy")
    wait_for_element: Optional[str] = Field(None, description="CSS selector to wait for after navigation (e.g. .cf-turnstile, #content)")
    include_html: bool = Field(True, description="Include page HTML in response")
    include_text: bool = Field(True, description="Include page text in response")
    include_screenshot: bool = Field(False, description="Include base64 screenshot in response")
    headers: Optional[dict[str, str]] = Field(None, description="Custom HTTP headers")
    cookies: Optional[list[dict]] = Field(None, description="Cookies to set before navigation")
    user_agent: Optional[str] = Field(None, description="Custom User-Agent string")
    viewport: Optional[dict] = Field(None, description="Viewport dimensions {width, height}")
    locale: Optional[str] = Field(None, description="Browser locale (e.g. en-US)")
    timezone: Optional[str] = Field(None, description="Timezone (e.g. America/New_York)")


class FetchRequest(BaseModel):
    url: str = Field(..., description="URL to fetch", min_length=1)
    session_id: Optional[str] = Field(None, description="Session ID for stateful context (cookies/localStorage persist)")
    options: Optional[FetchOptions] = None


class CookieItem(BaseModel):
    name: str
    value: str
    domain: Optional[str] = None
    path: Optional[str] = None
    httpOnly: Optional[bool] = None
    secure: Optional[bool] = None
    sameSite: Optional[str] = None


class Timing(BaseModel):
    navigation_ms: Optional[int] = None
    dom_content_loaded_ms: Optional[float] = None
    load_ms: Optional[float] = None


class FetchResponse(BaseModel):
    url: str
    status_code: Optional[int] = None
    title: Optional[str] = None
    html: Optional[str] = None
    text: Optional[str] = None
    screenshot: Optional[str] = Field(None, description="Base64-encoded full-page screenshot")
    cookies: Optional[list[CookieItem]] = None
    timing: Optional[Timing] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: str
    url: Optional[str] = None


class HealthResponse(BaseModel):
    status: str


class StatusResponse(BaseModel):
    status: str
    sessions_active: int
    sessions_max: int
    uptime_seconds: float
    timestamp: str
