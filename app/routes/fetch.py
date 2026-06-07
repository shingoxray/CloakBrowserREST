from __future__ import annotations

import asyncio
import base64
import logging
import time

from fastapi import APIRouter, Request
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout

from app.schemas import ErrorResponse, FetchRequest, FetchResponse

logger = logging.getLogger("cloakbrowser-rest.fetch")

router = APIRouter(tags=["fetch"])


@router.post(
    "/fetch",
    response_model=FetchResponse,
    responses={
        504: {"model": ErrorResponse, "description": "Navigation timeout"},
        502: {"model": ErrorResponse, "description": "Browser error"},
    },
)
async def fetch(request: Request, body: FetchRequest):
    bm = request.app.state.browser_manager
    opts = body.options

    timeout_ms = opts.timeout_ms if opts else 60000
    wait_until = opts.wait_until.value if opts else "networkidle"
    timeout_sec = timeout_ms / 1000

    humanize = opts.humanize if opts else False
    headless = opts.headless if opts else False

    try:
        async with asyncio.timeout(timeout_sec + 5):
            context = await bm.get_or_create_context(
                session_id=body.session_id,
                humanize=humanize,
                headless=headless,
                options=opts.model_dump() if opts else None,
            )

            page = await context.new_page()
            page.set_default_timeout(timeout_ms)

            try:
                result = await _fetch_page(page, context, body, timeout_ms, wait_until)
                return result
            finally:
                try:
                    await page.close()
                except PlaywrightError:
                    pass
    except asyncio.TimeoutError:
        logger.warning("Timeout fetching %s", body.url)
        return FetchResponse(
            url=body.url,
            error="navigation_timeout",
        )
    except PlaywrightTimeout:
        logger.warning("Playwright timeout fetching %s", body.url)
        return FetchResponse(
            url=body.url,
            error="navigation_timeout",
        )
    except PlaywrightError as e:
        logger.error("Browser error fetching %s: %s", body.url, e)
        return FetchResponse(
            url=body.url,
            error="browser_error",
        )


async def _fetch_page(page, context, body: FetchRequest, timeout_ms: int, wait_until: str):
    opts = body.options

    if opts and opts.headers:
        await page.set_extra_http_headers(opts.headers)

    if opts and opts.cookies:
        await context.add_cookies(opts.cookies)

    nav_start = time.monotonic()
    response = await page.goto(
        body.url,
        wait_until="domcontentloaded" if (opts and opts.wait_for_navigation) else wait_until,
        timeout=timeout_ms,
    )
    navigation_ms = int((time.monotonic() - nav_start) * 1000)

    if opts and opts.wait_for_element:
        await page.wait_for_selector(opts.wait_for_element, timeout=timeout_ms)
        logger.info("Waited for element: %s", opts.wait_for_element)

    if opts and opts.click:
        await page.click(opts.click, timeout=timeout_ms)
        logger.info("Clicked element: %s", opts.click)

    if opts and opts.wait_for_navigation:
        wait_start = time.monotonic()
        while time.monotonic() - wait_start < timeout_ms / 1000:
            await asyncio.sleep(0.5)
            try:
                await page.content()
            except PlaywrightError:
                continue
            title = await page.title()
            if title not in {"Just a moment...", "Checking your Browser...", "Checking your browser..."}:
                logger.info("Page passed challenge barrier (title=%s)", title)
                break

    title = await page.title()

    html = None
    if not opts or opts.include_html:
        html = await page.content()

    text = None
    if not opts or opts.include_text:
        text = await page.evaluate("document.body?.innerText ?? ''")

    screenshot = None
    if opts and opts.include_screenshot:
        screenshot_bytes = await page.screenshot(full_page=True)
        screenshot = base64.b64encode(screenshot_bytes).decode()

    cookies = await context.cookies()

    timing_data = await page.evaluate("""() => {
        const nav = performance.getEntriesByType('navigation')[0];
        if (!nav) return {};
        return {
            dom_content_loaded_ms: nav.domContentLoadedEventEnd - nav.startTime,
            load_ms: nav.loadEventEnd - nav.startTime,
        };
    }""")

    return FetchResponse(
        url=body.url,
        status_code=response.status if response else None,
        title=title,
        html=html,
        text=text,
        screenshot=screenshot,
        cookies=cookies,
        timing={
            "navigation_ms": navigation_ms,
            "dom_content_loaded_ms": timing_data.get("dom_content_loaded_ms"),
            "load_ms": timing_data.get("load_ms"),
        },
    )
