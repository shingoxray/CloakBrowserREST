from __future__ import annotations

import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.browser_manager import BrowserConfig, BrowserManager
from app.routes import fetch, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cloakbrowser-rest")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = BrowserConfig.from_env()
    bm = BrowserManager(config)
    await bm.start()

    eviction_task = asyncio.create_task(bm.eviction_loop())

    app.state.browser_manager = bm
    logger.info("CloakBrowser REST API started")

    yield

    eviction_task.cancel()
    await bm.stop()
    logger.info("CloakBrowser REST API shut down")


app = FastAPI(
    title="CloakBrowser REST API",
    description="Stealth web scraping via CloakBrowser. "
    "POST /fetch to retrieve webpage content with a browser that passes "
    "bot detection systems (reCAPTCHA v3, Cloudflare Turnstile, FingerprintJS).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(fetch.router)
