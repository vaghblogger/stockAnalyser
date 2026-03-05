# Stock Analysis Agent (LangGraph + Python API)

LangGraph-orchestrated workflow for **Indian market (NSE/BSE)** daily chart analysis: free data (yfinance), technical indicators, sentiment, and buy/sell/hold signals with backtesting.

## Phase 1 (this repo)

- **Free data**: Yahoo Finance (yfinance) for NSE/BSE symbols (e.g. `RELIANCE.NS`, `TCS.NS`).
- **Cache**: OHLCV cached in **SQLite** (`data/cache/ohlcv.db`), one row per (symbol, date).
- **Python API**: FastAPI with `/ohlcv`, `/enrich`, `/sentiment`, `/trend`, `/risk`, `/backtest`, `/metrics`, and **POST /api/graph/analyze**, **POST /api/graph/backtest** (LangGraph workflows).
- **Indicators**: SMA/EMA, RSI, MACD, ATR, Bollinger Bands, OBV (configurable via `config/config.yaml`).
- **Sentiment**: RSS + keyword-based scoring (optional: add FinBERT via `transformers`).
- **Backtest**: Rolling date windows, rule-based signal, forward returns, win rate / Sharpe / drawdown.
- **Orchestration**: **LangGraph** in-process (analysis graph: OHLCV → enrich + sentiment → signal; backtest graph). No separate n8n server required.
- **Dashboard**: Refresh runs **one symbol at a time** with a per-row spinner; only **missing date ranges** are fetched (DB is checked first). Yahoo data is requested in **1-year chunks** to avoid API limits (10 years = 10 chunks). Dashboard always loads live data from the DB. Each row shows **Duration (days)** (days of OHLCV in cache). **POST /api/data/refresh-symbol** refreshes a single symbol incrementally.
- **CLI**: `run.py analyze --symbol RELIANCE --days 90`, `run.py backtest ...`, `run.py analyze-graph --symbol RELIANCE --days 90`, `run.py backtest-graph --symbol RELIANCE --start 2023-01-01 --end 2024-06-01`.

## Quick start

1. **Create venv and install**
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. **Run the API**
   ```bash
   .venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000
   ```

3. **CLI (with API running)**
   ```bash
   .venv/bin/python run.py analyze --symbol RELIANCE --days 90
   .venv/bin/python run.py backtest --symbol RELIANCE --start 2023-01-01 --end 2024-06-01
   .venv/bin/python run.py analyze-graph --symbol RELIANCE --days 90
   .venv/bin/python run.py backtest-graph --symbol RELIANCE --start 2023-01-01 --end 2024-06-01
   ```

4. **Graph API**: Use **POST /api/graph/analyze** and **POST /api/graph/backtest** (see `http://127.0.0.1:8000/docs`). Legacy n8n workflow JSONs remain in `n8n/workflows/` for reference (deprecated).

## Config

- `config/config.yaml`: providers, indicator params, backtest defaults, API port.
- `config/symbols.csv`: symbol → yahoo_symbol, company_name (for sentiment and display).
- Env overrides: `DATA_PROVIDER`, `SENTIMENT_PROVIDER`, `CACHE_DIR`, `API_BASE`.

## Project layout

- `src/api/`: FastAPI app and routes.
- `src/data/`: Data provider interface, yfinance, cache, symbol resolution.
- `src/sentiment/`: Sentiment provider interface, free news + keyword/FinBERT.
- `src/analysis/`: Indicators, volume/structure, trend, risk.
- `src/backtest/`: Runner and metrics.
- `config/`: config.yaml, symbols.csv.
- `data/cache/`: SQLite DB `ohlcv.db` for OHLCV cache.
- `src/graph/`: LangGraph state, analysis graph, backtest graph.
- `n8n/workflows/`: Legacy n8n workflow JSONs (deprecated).

## Phase 2 (later)

Paid data (Alpha Vantage, EODHD, etc.), broker execution (Zerodha Kite / Upstox), position sizing, notifications (Slack/Telegram).
