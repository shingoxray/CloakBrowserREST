from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

from cloakbrowser import launch_async
from cloakbrowser.human import patch_context_async
from cloakbrowser.human.config import resolve_config

logger = logging.getLogger("cloakbrowser-rest.browser")


@dataclass
class BrowserConfig:
    headless: bool = False
    max_sessions: int = 100
    session_ttl_seconds: int = 600
    default_timeout_ms: int = 60000
    default_wait_until: str = "networkidle"
    proxy: Optional[str] = None

    @classmethod
    def from_env(cls) -> BrowserConfig:
        return cls(
            headless=os.environ.get("BROWSER_HEADLESS", "").lower() in ("true", "1", "yes"),
            max_sessions=int(os.environ.get("MAX_SESSIONS", "100")),
            session_ttl_seconds=int(os.environ.get("SESSION_TTL_MINUTES", "10")) * 60,
            default_timeout_ms=int(os.environ.get("DEFAULT_TIMEOUT_MS", "60000")),
            default_wait_until=os.environ.get("DEFAULT_WAIT_UNTIL", "networkidle"),
            proxy=os.environ.get("PROXY") or None,
        )


@dataclass
class ContextEntry:
    context: any
    created_at: float
    last_used: float
    options: dict
    humanize: bool = False
    headless: bool = False


class BrowserManager:
    def __init__(self, config: BrowserConfig):
        self._config = config
        self._browser = None
        self._alt_browser = None
        self._alt_headless: Optional[bool] = None
        self._contexts: dict[str, ContextEntry] = {}
        self._lock = asyncio.Lock()
        self._start_time = 0.0
        self._stopped = False

    async def start(self):
        logger.info(
            "Launching stealth browser (headless=%s%s)",
            self._config.headless,
            f", proxy={self._config.proxy}" if self._config.proxy else "",
        )
        self._browser = await launch_async(
            headless=self._config.headless,
            proxy=self._config.proxy,
            humanize=False,
        )
        self._start_time = time.monotonic()
        logger.info("Stealth browser launched")

    async def _ensure_browser(self, headless: bool):
        if headless == self._config.headless:
            return self._browser
        if self._alt_browser is not None and self._alt_headless == headless:
            return self._alt_browser
        if self._alt_browser is not None:
            logger.info("Closing alt browser (headless=%s) for new alt (headless=%s)",
                         self._alt_headless, headless)
            await self._alt_browser.close()
            self._alt_browser = None
        logger.info("Launching alt browser (headless=%s)", headless)
        self._alt_browser = await launch_async(
            headless=headless,
            proxy=self._config.proxy,
            humanize=False,
        )
        self._alt_headless = headless
        return self._alt_browser

    async def get_or_create_context(
        self,
        session_id: Optional[str],
        humanize: bool = False,
        headless: bool = False,
        options: Optional[dict] = None,
    ) -> any:
        if session_id and session_id in self._contexts:
            entry = self._contexts[session_id]
            if entry.humanize != humanize:
                logger.warning(
                    "Session %s was created with humanize=%s, ignoring requested humanize=%s (first-call-wins)",
                    session_id, entry.humanize, humanize,
                )
            if entry.headless != headless:
                logger.warning(
                    "Session %s was created with headless=%s, ignoring requested headless=%s (first-call-wins)",
                    session_id, entry.headless, headless,
                )
            entry.last_used = time.monotonic()
            return entry.context

        async with self._lock:
            if self._stopped:
                raise RuntimeError("Browser is shutting down")

            if session_id and session_id in self._contexts:
                entry = self._contexts[session_id]
                entry.last_used = time.monotonic()
                return entry.context

            if len(self._contexts) >= self._config.max_sessions:
                self._evict_one()

            browser = await self._ensure_browser(headless)
            ctx_options = self._build_context_options(options or {})
            context = await browser.new_context(**ctx_options)

            if humanize:
                cfg = resolve_config("default")
                patch_context_async(context, cfg)
                logger.info("Applied humanize patches to context%s",
                            f" ({session_id})" if session_id else "")

            if session_id:
                self._contexts[session_id] = ContextEntry(
                    context=context,
                    created_at=time.monotonic(),
                    last_used=time.monotonic(),
                    options=ctx_options,
                    humanize=humanize,
                    headless=headless,
                )
                logger.info("Created session context: %s", session_id)

            return context

    @staticmethod
    def _build_context_options(options: dict) -> dict:
        ctx_opts = {}
        if proxy := options.get("proxy"):
            ctx_opts["proxy"] = {"server": proxy}
        if ua := options.get("user_agent"):
            ctx_opts["user_agent"] = ua
        if viewport := options.get("viewport"):
            ctx_opts["viewport"] = viewport
        if locale := options.get("locale"):
            ctx_opts["locale"] = locale
        if timezone := options.get("timezone"):
            ctx_opts["timezone_id"] = timezone
        return ctx_opts

    def _evict_one(self):
        if not self._contexts:
            return
        now = time.monotonic()
        oldest_id = None
        oldest_used = float("inf")
        for sid, entry in self._contexts.items():
            if entry.last_used < oldest_used:
                oldest_used = entry.last_used
                oldest_id = sid
        if oldest_id:
            logger.info("Evicting stale session context: %s", oldest_id)
            entry = self._contexts.pop(oldest_id)
            asyncio.create_task(entry.context.close())

    async def _evict_stale(self):
        now = time.monotonic()
        stale_ids = [
            sid
            for sid, entry in self._contexts.items()
            if now - entry.last_used > self._config.session_ttl_seconds
        ]
        for sid in stale_ids:
            entry = self._contexts.pop(sid, None)
            if entry:
                logger.info("Evicting idle session context: %s", sid)
                await entry.context.close()

    async def eviction_loop(self, interval: float = 60.0):
        while not self._stopped:
            await asyncio.sleep(interval)
            try:
                await self._evict_stale()
            except Exception:
                logger.exception("Error during context eviction")

    async def close_context(self, session_id: str):
        entry = self._contexts.pop(session_id, None)
        if entry:
            await entry.context.close()
            logger.info("Closed session context: %s", session_id)

    async def stop(self):
        self._stopped = True
        for sid in list(self._contexts.keys()):
            await self.close_context(sid)
        if self._browser:
            await self._browser.close()
            logger.info("Stealth browser closed")
        if self._alt_browser:
            await self._alt_browser.close()
            logger.info("Alt browser closed")

    @property
    def active_session_count(self) -> int:
        return len(self._contexts)

    @property
    def uptime_seconds(self) -> float:
        if self._start_time == 0:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def is_ready(self) -> bool:
        return self._browser is not None and not self._stopped
