# CloakBrowser REST API

A REST API Docker container wrapping [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) — stealth Chromium with 58 C++ fingerprint patches that passes reCAPTCHA v3 (score 0.9), Cloudflare Turnstile, FingerprintJS, and 30+ bot detection systems.

```bash
docker compose up
curl http://localhost:3412/fetch \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

## API

### `POST /fetch`

Fetch a webpage with a stealth browser.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | — | **Required.** Target URL |
| `session_id` | string | `null` | Session ID for stateful context (cookies, localStorage persist) |
| `options.proxy` | string | `null` | Proxy URL (e.g. `http://user:pass@host:8080`) |
| `options.geoip` | bool | `false` | Auto-detect timezone/locale from proxy IP |
| `options.humanize` | bool | `false` | Enable human-like mouse/keyboard/scroll behavior |
| `options.headless` | bool | `false` | Run browser headless (no Xvfb display) |
| `options.timeout_ms` | int | `60000` | Navigation timeout in milliseconds (1000–120000) |
| `options.wait_until` | string | `"networkidle"` | Playwright waitUntil strategy: `load`, `domcontentloaded`, `networkidle`, `commit` |
| `options.wait_for_element` | string | `null` | CSS selector to wait for after navigation |
| `options.click` | string | `null` | CSS selector to click after navigation |
| `options.wait_for_navigation` | bool | `false` | Wait for Cloudflare challenge / redirect to complete |
| `options.include_html` | bool | `true` | Include page HTML in response |
| `options.include_text` | bool | `true` | Include page text in response |
| `options.include_screenshot` | bool | `false` | Include base64 full-page screenshot in response |
| `options.headers` | object | `null` | Custom HTTP headers (`{"Authorization": "Bearer ..."}`) |
| `options.cookies` | array | `null` | Cookies to set before navigation |
| `options.user_agent` | string | `null` | Custom User-Agent string |
| `options.viewport` | object | `1920×1080` | Viewport dimensions (`{"width": 1920, "height": 1080}`) |
| `options.locale` | string | `"en-US"` | Browser locale (e.g. `en-US`) |
| `options.timezone` | string | `"America/New_York"` | Timezone (e.g. `America/New_York`) |

**Minimal request** (everything defaults):
```json
{"url": "https://example.com"}
```

**Response:**

```json
{
  "url": "https://example.com",
  "status_code": 200,
  "title": "Example Domain",
  "html": "<html>...</html>",
  "text": "Example Domain...",
  "screenshot": "base64...",
  "cookies": [{"name": "...", "value": "..."}],
  "timing": {"navigation_ms": 954, "dom_content_loaded_ms": 439, "load_ms": 440},
  "error": null
}
```

### `GET /health`

```json
{"status": "ok"}
```

### `GET /status`

```json
{"status": "ok", "sessions_active": 0, "sessions_max": 100, "uptime_seconds": 13.7, "timestamp": "..."}
```

Interactive docs at [http://localhost:3412/docs](http://localhost:3412/docs).

## Sessions

Pass an optional `session_id` to persist cookies, localStorage, and IndexedDB across requests. Contexts are isolated — use different IDs for separate sessions. Sessions idle longer than `SESSION_TTL_MINUTES` (default 10) are evicted automatically. Max `MAX_SESSIONS` (default 100).

## Cloudflare Challenge Handling

Set `"wait_for_navigation": true` to automatically wait for Cloudflare managed challenges (Turnstile, JS challenge) to complete before returning page content. The browser:

1. Navigates to the URL (initial HTTP 403 response is normal)
2. Polls page content every 500ms, retrying silently during post-challenge redirects
3. Detects challenge completion when the page title changes from `"Just a moment..."` to the real page title
4. Returns the final content with all cookies (`cf_clearance`) intact

**Default context options** (viewport 1920×1080, locale `en-US`, timezone `America/New_York`) are auto-applied — these are required for Cloudflare's challenge to complete. Without them, Turnstile passes but the `cf_clearance` cookie is never set and the page never redirects.

```json
{
  "url": "https://bt4gprx.com/search?q=test",
  "options": {
    "wait_for_navigation": true,
    "timeout_ms": 60000
  }
}
```

Note: Cloudflare challenges may fail through certain proxies due to latency. The typical challenge takes ~7s to complete with a direct connection.

## Humanize

Set `"humanize": true` in options to enable CloakBrowser's human-like behavior — Bézier mouse curves, per-character typing with realistic timing, and natural scrolling. Applied per-context via `patch_context_async` — no performance impact on non-humanized requests.

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `SERVER_HOST` | `0.0.0.0` | Bind address |
| `SERVER_PORT` | `3412` | Bind port |
| `BROWSER_HEADLESS` | `false` | Headless vs headed (Xvfb) |
| `MAX_SESSIONS` | `100` | Max concurrent contexts |
| `SESSION_TTL_MINUTES` | `10` | Idle session timeout |
| `DEFAULT_TIMEOUT_MS` | `60000` | Default page timeout |
| `DEFAULT_WAIT_UNTIL` | `networkidle` | Playwright wait strategy |
| `PROXY` | — | Default proxy for all requests |
| `CLOAKBROWSER_BINARY_PATH` | — | Custom Chromium binary path |

## Quick Start

```bash
git clone git@github.com:shingoxray/CloakBrowserREST.git
cd CloakBrowserREST
docker compose up -d
curl http://localhost:3412/health
```

## How It Works

A single stealth Chromium browser is launched at container startup. Each `/fetch` request opens a new page within an isolated browser context, navigates to the target URL, extracts content (HTML, text, screenshot), then closes the page. The underlying CloakBrowser binary has 58 source-level C++ patches — no JS injection, no flag hacks.

## Credits

Built on [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) by [CloakHQ](https://github.com/CloakHQ) — stealth Chromium with 58 source-level C++ fingerprint patches.

## License

MIT
