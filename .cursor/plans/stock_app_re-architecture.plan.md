---
name: Stock App Re-architecture
overview: "Re-architect the Stock Analysis web app: Nifty 50 pre-seed + auto-refresh, configurable persisted dashboard, Analysis gauges, customizable backtest with saved strategies, Paper Trading (multi-portfolio, multi-strategy), global strategy template, and n8n workflow updates."
todos:
  - id: app-db
    content: Create app.db schema and CRUD for dashboard_views, strategies, paper portfolios/positions
    status: pending
  - id: universe-preseed
    content: Nifty 50 universe, pre-seed OHLCV on first run, store universe in app DB or config
    status: pending
  - id: scheduler
    content: APScheduler for configurable-interval refresh of all universe symbols
    status: pending
  - id: dashboard-persist
    content: Dashboard column config API + frontend picker; persist and restore view from app DB
    status: pending
  - id: strategies-api
    content: Strategies CRUD API + global default; wire backtest to use strategy ID and params
    status: pending
  - id: backtest-multi
    content: Backtest multi-symbol, per-stock strategy dropdown, Save as strategy
    status: pending
  - id: analysis-gauges
    content: Analysis page per-indicator gauges (needle) + optional summary gauge
    status: pending
  - id: paper-trading
    content: Paper portfolios/positions CRUD, paper engine (signals → virtual trades), UI and run API
    status: pending
  - id: n8n-updates
    content: Update backtest workflow for new API; optional workflows for strategies and paper run; update ARCHITECTURE.md
    status: pending
isProject: false
---

# Stock Analysis Web App – Re-architecture Plan

## Target architecture (high level)

- **Data**: Pre-seed Nifty 50 + custom symbols; auto-refresh at configurable interval; all in `ohlcv.db`.
- **App state**: New `app.db` for dashboard views, strategies, paper portfolios, paper trades.
- **Dashboard**: Configurable columns (add/remove/reorder indicators), persisted and restored on launch.
- **Analysis**: Per-indicator gauges with needle (Buy/Sell/Hold) + optional composite needle.
- **Backtest**: Multi-symbol, per-stock strategy selection, save strategies; global default (template) for new stocks.
- **Paper Trading**: Multiple portfolios; per-stock one or more strategies; run simulation from API or UI.
- **n8n**: Existing analysis workflow unchanged; backtest workflow updated for new API; optional new nodes for strategies/paper.

---

## 1. Data layer: Nifty 50 + auto-refresh

- **Universe**: Nifty 50 list (e.g. `config/nifty50.csv` or `symbols.csv`); ability to add more symbols; universe stored so refresh knows what to update.
- **Pre-seed**: On first run, fetch and store OHLCV for all universe symbols (e.g. 1–2 years); use existing cache write.
- **Scheduler**: APScheduler in app lifespan; config: `refresh_interval_minutes`, `refresh_enabled`, `refresh_lookback_days`. Job: for each symbol, fetch missing dates and upsert into `ohlcv.db`.

## 2. App DB (app.db)

- **Tables**: `dashboard_views` (columns_config JSON), `strategies` (name, params JSON, is_global_default), `paper_portfolios`, `paper_portfolio_positions` (symbol, strategy_ids JSON), `paper_trades` or equity snapshots.
- **APIs**: Dashboard views CRUD; Strategies CRUD; Paper portfolios and positions CRUD; run paper (e.g. POST run day).

## 3. Dashboard

- Columns config (which indicators, order) saved in app DB; column picker in UI; on load restore last/default view.

## 4. Analysis page

- Multiple gauges (one per indicator: RSI, MACD, Trend, etc.) with needle and Buy/Sell/Hold zones; optional single composite needle. Reuse existing interpret* logic.

## 5. Backtest

- Strategy = named record in DB (params JSON). Global default strategy for new stocks. Backtest request: symbols + strategy_assignments (per-symbol strategy_id or default). Save strategy from UI/API.

## 6. Paper trading

- Multiple portfolios; each with positions (symbol + list of strategy_ids). Paper engine runs signals, updates virtual positions, snapshots equity. Optionally run from n8n (e.g. scheduled).

## 7. Global vs stock-level strategy

- One strategy marked global default (template). Per-stock override in backtest and paper; if no override, use global default.

---

## 8. n8n architecture updates

### 8.1 What stays the same (no n8n change)

- **Stock Analysis workflow** (`stock_analysis_workflow.json`): `GET /ohlcv`, `POST /enrich`, `GET /sentiment` keep the same contracts. This workflow can remain unchanged. With pre-seed and scheduler, data for Nifty 50 will often already be in cache when n8n calls `/ohlcv`.

### 8.2 What must be updated in n8n

**Backtest workflow** (`n8n/workflows/stock_backtest_workflow.json`):

- **Current**: Sends single-symbol body: `symbol`, `start`, `end`, `lookback_days`, `hold_days`, `step_days`.
- **New API**: Support multi-symbol and strategy selection:
  - **Request**: Either keep backward compatibility (single `symbol`, optional `strategy_id`) or adopt new shape: e.g. `symbols` array, optional `strategy_assignments` (map of symbol → strategy_id), and optional `strategy_id` for single-symbol runs.
  - **Response**: May include per-symbol breakdown, strategy name, and aggregated metrics.

**Required n8n changes:**

- Update the **POST Backtest** node body to include optional `strategy_id` (and, when implemented, `symbols` and `strategy_assignments` if using multi-symbol).
- Update the **Report** (Set) node to handle the new response shape (e.g. `metrics`, `by_symbol`, `strategy`, `rows`) so downstream nodes or users see the right fields.

### 8.3 Optional n8n extensions (new workflows or nodes)

- **Strategies**: Call `GET /api/strategies` (list) or `GET /api/strategies/:id` (get one) so a workflow can choose a strategy by name/id before calling backtest or paper.
- **Paper trading**: Call e.g. `POST /api/paper/portfolios/:id/run` (or equivalent “run paper day” endpoint). A **Schedule** trigger can run this daily after market close so paper trading runs without opening the web app.
- **Refresh**: If the app exposes e.g. `POST /api/refresh` (or `/api/data/refresh`) for on-demand refresh, an n8n workflow could call it (e.g. after market close) in addition to the in-app scheduler.

### 8.4 Documentation updates

- **ARCHITECTURE.md**:
  - State that **data refresh** is handled by the **app’s scheduler**, not n8n.
  - Document the **new backtest** contract (multi-symbol, strategy_id / strategy_assignments, response shape).
  - List **new endpoints** (strategies, dashboard views, paper portfolios and run) so n8n users can call them.

### 8.5 Summary table (n8n)


| Item                     | Action                                                                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| Stock Analysis workflow  | No change required.                                                                                                 |
| Stock Backtest workflow  | **Update**: request body (and Report node) for new backtest API (strategy_id, optional multi-symbol, new response). |
| New workflows (optional) | Add nodes/workflows for strategies API and paper “run”; optional refresh trigger if exposed.                        |
| ARCHITECTURE.md          | Update data-refresh description, backtest contract, and new endpoints.                                              |


---

## 9. Implementation order

1. App DB + schema; minimal API for strategies and dashboard views.
2. Universe + pre-seed; scheduler for refresh.
3. Dashboard column config API + frontend; persist/restore from app DB.
4. Strategies API; wire backtest to strategy ID and params.
5. Backtest UI: multi-symbol, per-stock strategy, “Save as strategy”.
6. Analysis gauges (per-indicator + optional summary).
7. Paper trading: engine, CRUD, run API, UI.
8. **n8n**: Update backtest workflow and ARCHITECTURE.md; optionally add strategies/paper/refresh workflows.

---

## 10. Files to add or change (summary)


| Area      | Files / changes                                                                                        |
| --------- | ------------------------------------------------------------------------------------------------------ |
| Config    | `config/config.yaml`: refresh_interval_minutes, refresh_enabled, refresh_lookback_days.                |
| Data      | New: `src/data/universe.py`. Extend or keep `src/data/cache.py`.                                       |
| Scheduler | New: `src/scheduler.py` or `src/tasks/refresh.py`; start in `src/api/main.py` lifespan.                |
| App DB    | New: `src/db/app_db.py`, schema init, CRUD for views, strategies, portfolios, paper.                   |
| API       | New routes: dashboard_views, strategies, paper. Extend backtest route (multi-symbol, strategy_id).     |
| Frontend  | Dashboard column config; backtest symbol+strategy grid; Analysis gauges; Paper tab.                    |
| n8n       | Update `n8n/workflows/stock_backtest_workflow.json`; optional new workflows; update `ARCHITECTURE.md`. |


