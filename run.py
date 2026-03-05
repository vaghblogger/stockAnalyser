#!/usr/bin/env python3
"""
CLI for Stock Analysis Agent.
  python run.py analyze --symbol RELIANCE [--days 90]
  python run.py backtest --symbol RELIANCE --start 2023-01-01 --end 2024-06-01 [--lookback 90] [--hold-days 5] [--step-days 5]
  python run.py analyze-graph --symbol RELIANCE [--days 90]   # LangGraph analysis workflow
  python run.py backtest-graph --symbol RELIANCE --start ... --end ... [options]  # LangGraph backtest
Calls the Python API (assumes API is running on API_BASE or localhost:8000).
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode


def get_api_base() -> str:
    return os.environ.get("API_BASE", "http://localhost:8000")


def http_get(path: str, params: Optional[dict] = None) -> dict:
    url = get_api_base().rstrip("/") + path
    if params:
        url += "?" + urlencode(params)
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        print(f"HTTP error {e.code}: {e.reason}", file=sys.stderr)
        try:
            body = e.read().decode()
            print(body, file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)
    except URLError as e:
        print(f"Request failed: {e.reason}", file=sys.stderr)
        sys.exit(1)


def http_post(path: str, data: dict) -> dict:
    url = get_api_base().rstrip("/") + path
    body = json.dumps(data).encode()
    req = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        print(f"HTTP error {e.code}: {e.reason}", file=sys.stderr)
        try:
            print(e.read().decode(), file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)
    except URLError as e:
        print(f"Request failed: {e.reason}", file=sys.stderr)
        sys.exit(1)


def cmd_analyze(symbol: str, days: int) -> None:
    """Fetch OHLCV, enrich, sentiment, and print summary (no LLM; use API for full pipeline)."""
    end = date.today()
    start = end - timedelta(days=days)
    start_str = start.isoformat()
    end_str = end.isoformat()
    print(f"Fetching OHLCV {symbol} from {start_str} to {end_str}...")
    ohlcv_resp = http_get("/ohlcv", {"symbol": symbol, "start": start_str, "end": end_str, "days": days})
    ohlcv = ohlcv_resp.get("ohlcv", [])
    if not ohlcv:
        print("No OHLCV data.")
        return
    print(f"Got {len(ohlcv)} bars. Enriching...")
    enrich_resp = http_post("/enrich", {"ohlcv": ohlcv, "symbol": symbol})
    indicators = enrich_resp.get("indicators", {})
    print("Indicators (last):", json.dumps(indicators, indent=2))
    print("Volume:", enrich_resp.get("volume_summary", ""))
    print("Structure:", enrich_resp.get("structure_summary", ""))
    print("Fetching sentiment...")
    sent = http_get("/sentiment", {"symbol": symbol, "lookback_days": 7})
    print("Sentiment:", sent.get("label"), "score", sent.get("score"))


def cmd_backtest(
    symbol: str,
    start: str,
    end: str,
    lookback: int,
    hold_days: int,
    step_days: int,
) -> None:
    """Run backtest via API and print metrics."""
    print(f"Backtest {symbol} from {start} to {end} (lookback={lookback}, hold={hold_days}, step={step_days})...")
    resp = http_post(
        "/backtest",
        {
            "symbol": symbol,
            "start": start,
            "end": end,
            "lookback_days": lookback,
            "hold_days": hold_days,
            "step_days": step_days,
        },
    )
    metrics = resp.get("metrics", {})
    print("Metrics:", json.dumps(metrics, indent=2))
    rows = resp.get("rows", [])
    print(f"Total evaluation dates: {len(rows)}")


def cmd_analyze_graph(symbol: str, days: int) -> None:
    """Run analysis via LangGraph (POST /api/graph/analyze)."""
    print(f"Running analysis graph for {symbol} (days={days})...")
    resp = http_post("/api/graph/analyze", {"symbol": symbol, "days": days})
    print("Signal:", resp.get("signal", "HOLD"))
    print("Reason:", resp.get("reason", ""))
    if resp.get("enrich_result"):
        print("Indicators (sample):", json.dumps(resp["enrich_result"].get("indicators", {}) or {}, indent=2)[:500])
    if resp.get("sentiment_result"):
        print("Sentiment:", resp["sentiment_result"].get("label"), resp["sentiment_result"].get("score"))


def cmd_backtest_graph(
    symbol: str,
    start: str,
    end: str,
    lookback: int,
    hold_days: int,
    step_days: int,
    strategy_id: Optional[str] = None,
) -> None:
    """Run backtest via LangGraph (POST /api/graph/backtest)."""
    print(f"Backtest graph {symbol} from {start} to {end}...")
    body = {
        "symbol": symbol,
        "start": start,
        "end": end,
        "lookback_days": lookback,
        "hold_days": hold_days,
        "step_days": step_days,
    }
    if strategy_id:
        body["strategy_id"] = strategy_id
    resp = http_post("/api/graph/backtest", body)
    metrics = resp.get("metrics", {})
    print("Metrics:", json.dumps(metrics, indent=2))
    rows = resp.get("rows", [])
    print(f"Total evaluation dates: {len(rows)}")
    if resp.get("run_id"):
        print("Run ID:", resp["run_id"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock Analysis Agent CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    # analyze
    p_analyze = sub.add_parser("analyze", help="Fetch OHLCV, enrich, sentiment for symbol")
    p_analyze.add_argument("--symbol", "-s", required=True, help="Symbol (e.g. RELIANCE)")
    p_analyze.add_argument("--days", "-d", type=int, default=90, help="Lookback days")
    # backtest
    p_bt = sub.add_parser("backtest", help="Run backtest via API")
    p_bt.add_argument("--symbol", "-s", required=True)
    p_bt.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p_bt.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    p_bt.add_argument("--lookback", type=int, default=90)
    p_bt.add_argument("--hold-days", type=int, default=5)
    p_bt.add_argument("--step-days", type=int, default=5)
    # analyze-graph (LangGraph)
    p_ag = sub.add_parser("analyze-graph", help="Run analysis via LangGraph (POST /api/graph/analyze)")
    p_ag.add_argument("--symbol", "-s", required=True)
    p_ag.add_argument("--days", "-d", type=int, default=90)
    # backtest-graph (LangGraph)
    p_bg = sub.add_parser("backtest-graph", help="Run backtest via LangGraph (POST /api/graph/backtest)")
    p_bg.add_argument("--symbol", "-s", required=True)
    p_bg.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p_bg.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    p_bg.add_argument("--lookback", type=int, default=90)
    p_bg.add_argument("--hold-days", type=int, default=5)
    p_bg.add_argument("--step-days", type=int, default=5)
    p_bg.add_argument("--strategy-id", type=str, default=None, help="Optional strategy ID")
    args = parser.parse_args()
    if args.command == "analyze":
        cmd_analyze(args.symbol, args.days)
    elif args.command == "backtest":
        cmd_backtest(args.symbol, args.start, args.end, args.lookback, args.hold_days, args.step_days)
    elif args.command == "analyze-graph":
        cmd_analyze_graph(args.symbol, args.days)
    elif args.command == "backtest-graph":
        cmd_backtest_graph(
            args.symbol, args.start, args.end,
            args.lookback, args.hold_days, args.step_days,
            strategy_id=args.strategy_id,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
