# Summary of Changes (Worktree → Main Project)

This document describes all changes made to the Stock Analysis application so you can resume work elsewhere or replicate them.

---

## 1. Architecture: Migration from n8n to LangGraph

**Goal:** Replace external n8n workflow orchestration with in-process LangGraph workflows.

### 1.1 New dependency
- **`requirements.txt`**: Added `langgraph>=0.2.0` (or compatible version).

### 1.2 New package: `src/graph/`
- **`src/graph/state.py`**
  - `AnalysisState`: TypedDict for analysis flow (symbol, days, ohlcv, enrich_result, sentiment_result, signal, reason, error, etc.).
  - `BacktestState`: TypedDict for backtest flow (symbol/symbols, strategy_assignments, start, end, metrics, rows, etc.).
  - `GraphContext`: Holds app dependencies (config, cache_dir, data_provider, sentiment_provider) passed into graph nodes.
- **`src/graph/analysis_graph.py`**
  - LangGraph for “Stock Analysis”: nodes `fetch_ohlcv` → `enrich` and `fetch_sentiment` (parallel) → `merge_and_signal`.
  - Reuses logic from existing enrich/sentiment/backtest (e.g. rule-based signal from `_rule_signal`).
- **`src/graph/backtest_graph.py`**
  - LangGraph for “Stock Backtest”: single node that builds a `BacktestRequest` from state and calls `run_backtest_core`.
- **`src/graph/__init__.py`**
  - Exports: `build_analysis_graph`, `build_backtest_graph`, `AnalysisState`, `BacktestState`, `GraphContext`.

### 1.3 Backtest refactor for reuse
- **`src/api/routes/backtest.py`**
  - Core logic extracted into `run_backtest_core(...)` that accepts app context and request body.
  - Existing `POST /api/backtest` route calls `run_backtest_core`.
  - LangGraph backtest node also calls `run_backtest_core` after building the request from state.

### 1.4 New API routes
- **`src/api/routes/graph.py`** (new file)
  - `POST /api/graph/analyze`: body `{ "symbol", "days" }` → runs analysis graph, returns symbol, company_name, ohlcv_count, enrich_result, sentiment_result, signal, reason, error.
  - `POST /api/graph/backtest`: body same as `POST /api/backtest` → runs backtest graph, returns metrics, rows, strategy, by_symbol.
  - Both use `_context_from_request(request)` to build `GraphContext` from `request.app.state`.

### 1.5 Main app wiring
- **`src/api/main.py`**
  - Import and include: `from src.api.routes import ... graph` and `app.include_router(graph.router, prefix="", tags=["graph"])`.

### 1.6 CLI
- **`run.py`**
  - New subcommands: `analyze-graph` (POST to `/api/graph/analyze`) and `backtest-graph` (POST to `/api/graph/backtest`).

### 1.7 Docs
- **`ARCHITECTURE.md`**: Updated to describe LangGraph as the orchestration layer, new graph endpoints, and diagrams; n8n marked deprecated.
- **`README.md`**: Updated description, quick start, and project layout for LangGraph and graph endpoints.
- **`Commands`**: Removed n8n start instructions; added graph API and CLI usage.

---

## 2. UI/UX: Dashboard and App Shell

**Goal:** Dashboard first, configurable lookback, refresh-from-source, new column, and “Analyse” instead of “Edit”.

### 2.1 Tab order and default tab
- **`static/index.html`**
  - Navigation and sections reordered so **Dashboard** is the first tab and active by default.
  - Tab order: Dashboard → Analysis → Backtest → Strategies → Paper Trading → etc.

### 2.2 Lookback controls (Dashboard)
- **`static/index.html`**
  - Dashboard has a lookback control: **number input + unit selector** (Days / Months / Years), consistent with the Analysis tab.
- **`static/app.js`**
  - `getDashboardLookbackDays()`: Parses the dashboard lookback (value + unit) and returns total days.
  - `loadDashboard()` uses `getDashboardLookbackDays()` for the request (e.g. query or body as used by the backend).

### 2.3 Refresh button behavior
- **`static/app.js`**
  - “Refresh” on the dashboard:
    - Shows messages: “Refreshing data (fetching from source)…” and “Loading dashboard…”.
    - Calls `POST /api/data/seed` with the computed `lookback_days` (from dashboard lookback).
    - On success/failure, updates the dashboard summary (e.g. “Data refreshed. N symbol(s) updated.” or “Refresh failed: <error>”).
  - Dashboard fetch uses `cache: 'no-store'` and `Cache-Control`/`Pragma` headers to avoid browser cache.

### 2.4 “Data available from” column
- **`src/api/routes/dashboard.py`**
  - Each dashboard stock entry includes `data_available_from`: ISO date string of the minimum date in the OHLCV data for that symbol (or `None` if insufficient data).
- **`static/app.js`**
  - `DASHBOARD_AVAILABLE_COLUMNS` and default columns include `'data_available_from'`.
  - `buildDashboardHeader()` and row rendering show “Data available from” and `row.data_available_from`.
  - Column visibility modal includes the new column.

### 2.5 Edit removed, “Analyse” added
- **`static/index.html`** / **`static/app.js`**
  - “Edit” button removed from dashboard rows.
  - “Analyse” button added per row: on click, switches to the Analysis tab and pre-fills the symbol (e.g. `switchToAnalysisTabWithSymbol(symbol)`).

### 2.6 Version indicator
- **`static/index.html`**: In the app bar, added a visible version label (e.g. “· v2”) with a title attribute.
- **`static/styles.css`**: Styles for `.app-version` (e.g. font weight, size, opacity).

---

## 3. Cache-Busting and Serving /app

**Goal:** Ensure HTML, CSS, and JS always load the latest version when opening/refreshing the app (no stale cache).

### 3.1 Per-request cache buster
- **`src/api/main.py`**
  - `import time`.
  - `/app` and `/app/` no longer serve a static file; they use a function that:
    - Reads `static/index.html` from disk.
    - Replaces placeholder `__CACHE_BUST__` with a **per-request** value: `str(int(time.time() * 1000))`.
    - Returns the modified HTML with headers: `Cache-Control: no-store, no-cache, must-revalidate, max-age=0`, `Pragma: no-cache`, `Expires: 0`.
  - So every request to `/app` gets a new `?v=...` for assets, forcing the browser to fetch the latest CSS and JS.

### 3.2 Placeholders in HTML
- **`static/index.html`**
  - `<link rel="stylesheet" href="/static/styles.css?v=__CACHE_BUST__">`
  - `<script src="/static/app.js?v=__CACHE_BUST__"></script>`
  - In `<head>`: `<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">` and `<meta http-equiv="Pragma" content="no-cache">`.

### 3.3 No-cache middleware for static and /app
- **`src/api/main.py`**
  - `NoCacheStaticMiddleware`: After the response is generated, if the path starts with `/static/` or is `/app` or `/app/`, sets `Cache-Control` and `Pragma` to no-cache so the browser does not cache these responses.

---

## 4. Optional Test Script

- **`test_app_cache.py`** (in project root)
  - Uses FastAPI `TestClient` to hit `/app` and checks: 200, no-cache headers, presence of `app.js?v=...` and `styles.css?v=...`, and that repeated requests can get different `?v=` values (per-request bust).
  - Run from project root with `PYTHONPATH=.` so that `src` resolves.

---

## 5. Syncing Worktree to Main Project

All of the above was implemented in the **worktree** at:
`/Users/vagh/.cursor/worktrees/StockAnalysis/eof/`

To mirror these changes into the **main project** at:
`/Users/vagh/Cursor/StockAnalysis/`

the following was done (you can re-run or replicate as needed):

1. Create directory in main: `mkdir -p /Users/vagh/Cursor/StockAnalysis/src/graph`
2. Copy from worktree (`WT`) to main (`MAIN`):
   - `static/index.html`, `static/app.js`, `static/styles.css`
   - `src/api/main.py`, `src/api/routes/dashboard.py`, `src/api/routes/backtest.py`, `src/api/routes/graph.py`
   - `src/graph/__init__.py`, `src/graph/state.py`, `src/graph/analysis_graph.py`, `src/graph/backtest_graph.py`
   - `requirements.txt`, `run.py`, `ARCHITECTURE.md`, `README.md`, `Commands`
   - Optionally: `test_app_cache.py`

Run the app from the main project with:
```bash
cd /Users/vagh/Cursor/StockAnalysis
PYTHONPATH=. python3 -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```
Then open `http://127.0.0.1:8000/app`; a normal refresh should always load the latest HTML, CSS, and JS.

---

## 6. File Checklist (what was added or modified)

| Path | Change |
|------|--------|
| `requirements.txt` | Added langgraph |
| `run.py` | Added analyze-graph, backtest-graph CLI |
| `ARCHITECTURE.md` | LangGraph, graph endpoints, n8n deprecated |
| `README.md` | LangGraph, graph endpoints, quick start |
| `Commands` | Graph API/CLI, n8n removed |
| `static/index.html` | Dashboard first, lookback number+unit, cache-bust placeholders, meta no-cache, Analyse, version badge |
| `static/app.js` | getDashboardLookbackDays, refresh→seed, data_available_from column, Analyse button, no-cache fetch |
| `static/styles.css` | .app-version |
| `src/api/main.py` | time import, graph router, NoCacheStaticMiddleware, /app dynamic HTML with per-request cache bust |
| `src/api/routes/backtest.py` | run_backtest_core extracted for graph |
| `src/api/routes/dashboard.py` | data_available_from in response |
| `src/api/routes/graph.py` | **New**: POST /api/graph/analyze, POST /api/graph/backtest |
| `src/graph/__init__.py` | **New** |
| `src/graph/state.py` | **New** |
| `src/graph/analysis_graph.py` | **New** |
| `src/graph/backtest_graph.py` | **New** |
| `test_app_cache.py` | **New** (optional) |

---

*End of summary.*
