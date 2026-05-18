# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`douyin-clickview` is a Python CLI tool that simulates browser visits to Douyin (TikTok China) videos. It uses Playwright with mobile Safari emulation and anti-detection patches to mimic a real iPhone user watching, scrolling, and interacting with video pages.

## Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install Playwright Chromium browser
playwright install chromium

# Run the CLI
douyin-clickview --help
python -m douyin_clickview --help

# Run all tests
pytest

# Run a single test file
pytest tests/test_url_parser.py

# Run a single test by name
pytest -k "test_parse_raw_id"

# Lint
ruff check douyin_clickview/ tests/

# Type checking (if configured)
mypy douyin_clickview/
```

## Architecture

**Entry point**: `cli.py` uses Click to parse CLI args, then calls `asyncio.run(_run(...))`. The async flow is: load config → parse URL → schedule visits → print report.

**Config loading** (`config.py`): Pydantic `AppConfig` model validates all settings. `ConfigLoader.load()` merges four sources with priority: CLI flags > YAML config file > `DY_*` environment variables > Pydantic field defaults. CLI kebab-case flags like `--no-comment` and `--watch` are translated to snake_case config fields in `_clean_cli_kwargs`.

**URL parsing** (`url_parser.py`): `URLParser.parse()` handles 6 input formats: raw 19-digit video IDs, `douyin.com/video/` URLs, `v.douyin.com` short links (followed via 302 with httpx), `iesdouyin.com/share/` links, and URLs embedded in mixed Chinese/emoji text. Short links may chain through `iesdouyin.com` before reaching the final `douyin.com/video/` URL.

**Visit scheduling** (`engine/scheduler.py`): `Scheduler.run()` launches one browser context, then iterates `visit_count` times. Each visit runs through `_execute_with_retry`, which creates a `SingleVisitor` and retries on failure with exponential backoff (base 2s, doubling, + random jitter). Non-retryable errors (CAPTCHA, PageStructure, VideoNotFound) are not retried.

**Single visit** (`engine/visitor.py`): `SingleVisitor.execute()` runs a fixed sequence: navigate → wait for video element → micro-interactions during watch time → scroll to comments → click a random comment → view user profile → swipe to next video → close page. Each action is recorded in `_actions_completed`. On failure, it returns a `VisitResult` with error info rather than raising.

**Browser layer** (`browser/`):
- `manager.py`: Owns Playwright lifecycle — `launch()` starts Chromium with `--disable-blink-features=AutomationControlled`, `create_context()` builds a BrowserContext with iPhone Safari UA, mobile viewport, Beijing geolocation, and stealth patches.
- `stealth.py`: Injects JS to override `navigator.webdriver`, `navigator.plugins`, `window.chrome.runtime`, WebGL renderer strings, and permissions query. Also blocks analytics/tracking requests via `context.route`.
- `actions.py`: Stateless static methods on `PageActions` that interact with Douyin's DOM. Uses multi-level fallback selectors (e.g., `[data-e2e='video-player']`, `div[class*='xgplayer']`, `video`) to handle page structure changes. `micro_interactions` performs random micro-scrolls and taps during watch time. `simulate_next_video` does a multi-step smooth swipe gesture.

**Display** (`display/`): `ProgressDisplay` is a `rich.Live` async context manager that renders a real-time progress table (visits done/remaining, success/fail counts, ETA, error breakdown). `FinalReport` generates either a plain-text summary or structured JSON output.

**Error hierarchy** (`errors.py`): All exceptions inherit from `ClickViewError`. Specific types: `URLParseError`, `NetworkError`, `CaptchaError`, `RateLimitError`, `PageStructureError`, `BrowserError`, `VideoNotFoundError`, `ConfigError`, `VisitInterruptedError`.

## Key patterns

- All async — the browser, HTTP client, and CLI flow are `asyncio`-based.
- `BrowserContext` (not `Browser`) is shared across visits within a run to reuse cookies/storage. A new `Page` is created per visit and closed after.
- Pydantic validators on `AppConfig` enforce constraints (e.g., `action_delay_range` must be `[min, max]`).
- Playwright is imported lazily via `async_playwright().start()` — the import only happens at runtime.

## Configuration

Default search paths for YAML config: `./config.yaml` then `~/.douyin-clickview.yaml`. Environment variables use the `DY_` prefix (e.g., `DY_VISIT_COUNT=5`, `DY_HEADLESS=false`). See `config.example.yaml` for all available options.
