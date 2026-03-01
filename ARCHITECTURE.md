# Stock Analysis Agent — Architecture

n8n-orchestrated agent for **Indian market (NSE/BSE)** daily chart analysis: free data (yfinance), technical indicators, sentiment, and buy/sell/hold signals with backtesting.

---

## High-level system overview

```mermaid
flowchart TB
    subgraph Clients["Clients & orchestration"]
        CLI["CLI (run.py)"]
        Web["Web app (/app)"]
        n8n["n8n workflows"]
    end

    subgraph API["Python API (FastAPI)"]
        Routes["/ohlcv, /enrich, /sentiment, /trend, /risk\n/backtest, /dashboard, /health\n/api/dashboard/views, /api/strategies\n/api/paper, /api/data/seed, /api/data/universe"]
    end

    subgraph Core["Core services"]
        Data["Data layer\n(providers + cache)\n+ scheduler refresh"]
        Analysis["Analysis\n(indicators, trend, risk)"]
        Sentiment["Sentiment\n(providers)"]
        Backtest["Backtest\n(runner + metrics)"]
    end

    subgraph External["External"]
        Yahoo["Yahoo Finance\n(yfinance)"]
        RSS["RSS / News\n(sentiment)"]
    end

    CLI --> Routes
    Web --> Routes
    n8n -->|"HTTP GET/POST"| Routes

    Routes --> Data
    Routes --> Analysis
    Routes --> Sentiment
    Routes --> Backtest

    Data --> Yahoo
    Data --> Cache[(SQLite\nohlcv.db)]
    Sentiment --> RSS
    Backtest --> Data
    Backtest --> Analysis
```

- **CLI** and **Web app** call the API directly.
- **n8n** orchestrates multi-step workflows by calling the same API (e.g. OHLCV → Enrich + Sentiment → Merge → Signal).
- **API** uses config-driven **data**, **analysis**, **sentiment**, and **backtest** services; data is cached in SQLite.
- **Data refresh** is handled by the app’s **scheduler** (APScheduler), not n8n: at a configurable interval, OHLCV for all universe symbols is refreshed and written to the cache.
- **App DB** (`data/app.db`) stores dashboard views, strategies, symbol universe, paper portfolios/snapshots, and backtest run history.

---

## n8n in the architecture

n8n runs as a separate process and uses the Stock Analysis API as an HTTP backend. Set `API_BASE` (or use `http://127.0.0.1:8000` / `http://host.docker.internal:8000` if n8n is in Docker).

### n8n ↔ API flow

```mermaid
sequenceDiagram
    participant User
    participant n8n
    participant API as Python API

    User->>n8n: Trigger workflow (e.g. Manual)
    n8n->>API: GET /ohlcv?symbol=RELIANCE&days=90
    API->>n8n: { ohlcv, symbol, ... }
    par Enrich and Sentiment
        n8n->>API: POST /enrich { ohlcv, symbol }
        API->>n8n: { indicators, volume_summary, structure_summary }
        n8n->>API: GET /sentiment?symbol=...&lookback_days=7
        API->>n8n: { label, score, snippets }
    end
    n8n->>n8n: Merge → Set Output (signal, reason)
    n8n->>User: Result (e.g. signal=HOLD, reason=...)
```

### Stock Analysis workflow (n8n)

```mermaid
flowchart LR
    T["Manual Trigger"] --> OHLCV["Fetch OHLCV\nGET /ohlcv"]
    OHLCV --> Enrich["Enrich Indicators\nPOST /enrich"]
    OHLCV --> Sentiment["Fetch Sentiment\nGET /sentiment"]
    Enrich --> Merge["Merge"]
    Sentiment --> Merge
    Merge --> Out["Set Output\n(signal, reason)"]
```

### Stock Backtest workflow (n8n)

```mermaid
flowchart LR
    T["Manual Trigger"] --> BT["POST Backtest\nPOST /backtest"]
    BT --> Report["Report\n(metrics, rows_count, strategy, by_symbol)"]
```

- **Backtest request** may include optional `strategy_id` (saved strategy) or `symbols` + `strategy_assignments` for multi-symbol runs. If omitted, the global default strategy is used.
- **Response** includes `metrics`, `rows`, `strategy` (name, description), and optionally `by_symbol` (per-symbol metrics).

Workflow JSONs: `n8n/workflows/stock_analysis_workflow.json`, `n8n/workflows/stock_backtest_workflow.json`.

### New API endpoints (re-architecture)

- **Dashboard views**: `GET/POST /api/dashboard/views`, `GET/PUT/DELETE /api/dashboard/views/:id` — persist/restore column config.
- **Strategies**: `GET/POST /api/strategies`, `GET/PUT/DELETE /api/strategies/:id`, `POST /api/strategies/:id/set-default` — CRUD and global default.
- **Paper trading**: `GET/POST /api/paper/portfolios`, `GET/PUT/DELETE /api/paper/portfolios/:id`, positions and `POST .../run`, `GET .../snapshots`.
- **Data**: `POST /api/data/seed` — pre-seed OHLCV for universe; `GET/POST/DELETE /api/data/universe` — list/add/remove symbols.

---

## Component layers

```mermaid
flowchart TB
    subgraph Entry["Entry points"]
        Main["src.api.main (FastAPI)"]
        Run["run.py (CLI)"]
    end

    subgraph API_Layer["API layer"]
        OHLCV_R["routes/ohlcv"]
        Enrich_R["routes/enrich"]
        Sentiment_R["routes/sentiment"]
        Trend_R["routes/trend"]
        Risk_R["routes/risk"]
        Backtest_R["routes/backtest"]
        Dashboard_R["routes/dashboard"]
    end

    subgraph Data_Layer["Data layer"]
        Cache["data/cache.py\n(SQLite OHLCV)"]
        Prov["data/providers\n(DataProvider)"]
        YahooProv["yahoo.py (yfinance)"]
    end

    subgraph Analysis_Layer["Analysis layer"]
        Ind["analysis/indicators.py"]
        Vol["analysis/volume_structure.py"]
        Trend_A["analysis/trend.py"]
        Risk_A["analysis/risk.py"]
    end

    subgraph Sentiment_Layer["Sentiment layer"]
        SentBase["sentiment/providers/base"]
        SentReg["sentiment/providers/registry"]
        FreeNews["free_news_finbert.py"]
    end

    subgraph Backtest_Layer["Backtest layer"]
        Runner["backtest/runner.py"]
        Metrics["backtest/metrics.py"]
    end

    subgraph Config["Config & state"]
        ConfigLoader["config_loader.py"]
        State["state.py (Pydantic)"]
        YAML["config/config.yaml"]
    end

    Main --> API_Layer
    Run --> Main

    OHLCV_R --> Data_Layer
    Enrich_R --> Analysis_Layer
    Sentiment_R --> Sentiment_Layer
    Trend_R --> Analysis_Layer
    Risk_R --> Analysis_Layer
    Backtest_R --> Backtest_Layer
    Backtest_R --> Data_Layer
    Backtest_R --> Analysis_Layer
    Dashboard_R --> Data_Layer
    Dashboard_R --> Analysis_Layer

    Prov --> YahooProv
    OHLCV_R --> Cache
    ConfigLoader --> YAML
    ConfigLoader --> State
```

---

## Data flow (analyse path)

End-to-end path used by both the API (and thus n8n) and the CLI `analyze` command:

```mermaid
flowchart LR
    subgraph Input
        Sym["symbol + date range"]
    end

    subgraph API_or_CLI["API (or CLI via API)"]
        A1["GET /ohlcv"]
        A2["POST /enrich"]
        A3["GET /sentiment"]
    end

    subgraph Data
        Resolve["Symbol resolution\n(.NS suffix)"]
        Cache[(cache)]
        Yahoo["yfinance"]
    end

    subgraph Enrichment
        Indicators["SMA, EMA, RSI\nMACD, ATR, BB, OBV"]
        Volume["volume_summary"]
        Structure["structure_summary"]
    end

    subgraph Sentiment
        RSS["RSS + keyword/FinBERT"]
        Score["label + score"]
    end

    Sym --> A1
    A1 --> Resolve
    Resolve --> Cache
    Cache -->|miss| Yahoo
    Yahoo --> Cache
    Cache --> A1
    A1 --> A2
    A2 --> Indicators
    A2 --> Volume
    A2 --> Structure
    A1 --> A3
    A3 --> RSS
    RSS --> Score
```

---

## Backtest flow

Used by `POST /backtest` and the n8n backtest workflow:

```mermaid
flowchart TB
    subgraph Input
        Params["symbol, start, end\nlookback_days, hold_days, step_days"]
    end

    subgraph Runner["backtest/runner"]
        EvalDates["generate_eval_dates"]
        Loop["For each eval_date"]
        Window["window = eval_date - lookback_days .. eval_date"]
        RunAnalysis["run_analysis(symbol, window)"]
        Forward["get_forward_return(symbol, eval_date, hold_days)"]
        Rows["rows: date, action, forward_return"]
    end

    subgraph Metrics["backtest/metrics"]
        WinRate["win_rate"]
        AvgRet["average_return"]
        Sharpe["sharpe_ratio"]
        DD["max_drawdown"]
    end

    Params --> EvalDates
    EvalDates --> Loop
    Loop --> Window
    Window --> RunAnalysis
    RunAnalysis --> Forward
    Forward --> Rows
    Rows --> Metrics
```

Strategy logic: if a strategy’s `params` include `buy_rule` and/or `sell_rule`, the **rule engine** (`src/analysis/rule_engine.py`) evaluates them; otherwise the built-in RSI/MACD/SMA rules are used. Rules use indicator names, flags, and operators (`<`, `<=`, `>`, `>=`, `==`, `!=`, `and`, `or`, `not`) in a TradingView Pine–style format. See **docs/BACKTEST_RULES.md** and **GET /backtest/rule-schema** for the full schema.

**Backtest history**: Every `POST /backtest` run is persisted in `backtest_runs` (app.db). **GET /backtest/history** lists runs (optional `limit`, `offset`, `symbol`, `strategy_id`); **GET /backtest/history/{run_id}** returns a full run (same shape as POST response) so the UI can display it. The Backtest tab includes a History section to list and view past runs.

---

## Project layout

```mermaid
flowchart LR
    subgraph Root["StockAnalysis/"]
        run["run.py"]
        req["requirements.txt"]
        cfg["config/"]
        data_dir["data/cache/"]
        static["static/"]
        n8n_dir["n8n/workflows/"]
        src["src/"]
    end

    subgraph config["config/"]
        yaml["config.yaml"]
        sym["symbols.csv"]
    end

    subgraph src_detail["src/"]
        api["api/"]
        data["data/"]
        analysis["analysis/"]
        sentiment["sentiment/"]
        backtest["backtest/"]
        state["state.py"]
        config_loader["config_loader.py"]
    end

    subgraph api_r["api/"]
        main["main.py"]
        routes["routes/"]
    end

    subgraph routes["routes/"]
        ohlcv["ohlcv.py"]
        enrich["enrich.py"]
        sentiment["sentiment.py"]
        trend["trend.py"]
        risk["risk.py"]
        backtest_r["backtest.py"]
        dashboard["dashboard.py"]
    end
```

| Path | Purpose |
|------|--------|
| `run.py` | CLI: `analyze`, `backtest` (calls API) |
| `config/config.yaml` | Providers, indicators, backtest defaults, API port |
| `config/symbols.csv` | symbol → yahoo_symbol, company_name |
| `data/cache/ohlcv.db` | SQLite OHLCV cache |
| `data/app.db` | App DB: dashboard views, strategies, universe, paper portfolios, backtest runs |
| `config/nifty50.csv` | Nifty 50 symbol list (default universe) |
| `static/` | Web app (index.html, app.js, styles.css) |
| `n8n/workflows/` | n8n workflow JSONs (analysis, backtest) |
| `src/api/main.py` | FastAPI app, lifespan, CORS, static mount, scheduler start/stop |
| `src/api/routes/*` | Route handlers (ohlcv, enrich, backtest, dashboard, dashboard_views, strategies, paper, data) |
| `src/data/` | Cache + data provider (yfinance) + universe (universe.py) |
| `src/db/` | App DB schema and CRUD (app_db.py) |
| `src/scheduler.py` | APScheduler for periodic OHLCV refresh |
| `src/paper/` | Paper trading engine |
| `src/analysis/` | Indicators, volume/structure, trend, risk |
| `src/sentiment/` | Sentiment provider (RSS + keyword/FinBERT) |
| `src/backtest/` | Runner + metrics |
| `src/state.py` | Pydantic models (config, Signal, SentimentResult) |
| `src/config_loader.py` | Load YAML + env overrides → AppConfig |

---

## Configuration and env overrides

Config is loaded from `config/config.yaml` and validated with Pydantic (`src/state.AppConfig`). Refresh (scheduler) options in config: `refresh.refresh_enabled`, `refresh.refresh_interval_minutes`, `refresh.refresh_lookback_days`. Environment overrides:

- `DATA_PROVIDER` — e.g. `yfinance`
- `SENTIMENT_PROVIDER` — e.g. `free_news_finbert`
- `CACHE_DIR` — cache directory path
- `API_PORT` — API server port
- `API_BASE` — used by CLI and n8n to call the API (e.g. `http://localhost:8000`)

---

## Summary

- **Single backend**: One FastAPI app serves REST endpoints, static web app, and is used by both CLI and n8n.
- **Data refresh**: Scheduler (APScheduler) runs at a configurable interval to refresh OHLCV for all universe symbols; universe is stored in app DB and seeded from config/nifty50.csv when empty.
- **n8n**: Orchestrates analysis (OHLCV → Enrich + Sentiment → Merge → Output) and backtest (POST /backtest, optional strategy_id; response includes strategy, by_symbol) via HTTP; no direct DB access.
- **Layers**: API → Data (providers + SQLite cache + universe), App DB (views, strategies, paper), Analysis, Sentiment, Backtest, Paper engine; Scheduler refreshes cache from universe.
- **Config**: YAML + env; all behaviour (providers, indicator params, backtest defaults) is config-driven.
