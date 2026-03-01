# Stock Analysis Agent (n8n + Python API)

n8n-orchestrated agentic workflow for **Indian market (NSE/BSE)** daily chart analysis: free data (yfinance), technical indicators, sentiment, and buy/sell/hold signals with backtesting.

## Phase 1 (this repo)

- **Free data**: Yahoo Finance (yfinance) for NSE/BSE symbols (e.g. `RELIANCE.NS`, `TCS.NS`).
- **Cache**: OHLCV cached in **SQLite** (`data/cache/ohlcv.db`), one row per (symbol, date).
- **Python API**: FastAPI with `/ohlcv`, `/enrich`, `/sentiment`, `/trend`, `/risk`, `/backtest`, `/metrics`.
- **Indicators**: SMA/EMA, RSI, MACD, ATR, Bollinger Bands, OBV (configurable via `config/config.yaml`).
- **Sentiment**: RSS + keyword-based scoring (optional: add FinBERT via `transformers`).
- **Backtest**: Rolling date windows, rule-based signal, forward returns, win rate / Sharpe / drawdown.
- **n8n**: Workflows in `n8n/workflows/` (import into n8n); set env `API_BASE=http://localhost:8000`.
- **CLI**: `run.py analyze --symbol RELIANCE --days 90` and `run.py backtest --symbol RELIANCE --start 2023-01-01 --end 2024-06-01`.

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
   ```

4. **n8n**: Run n8n locally, set `API_BASE=http://localhost:8000` (or `http://host.docker.internal:8000` if n8n is in Docker). Import `n8n/workflows/stock_analysis_workflow.json` and `stock_backtest_workflow.json`.

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
- `n8n/workflows/`: n8n workflow JSONs.

## Phase 2 (later)

Paid data (Alpha Vantage, EODHD, etc.), broker execution (Zerodha Kite / Upstox), position sizing, notifications (Slack/Telegram).
