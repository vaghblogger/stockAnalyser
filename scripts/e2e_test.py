#!/usr/bin/env python3
"""End-to-end test: OHLCV -> Enrich (indicators) -> Sentiment. Run with API up: uvicorn src.api.main:app --host 0.0.0.0 --port 8000"""

import json
import sys
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE = "http://127.0.0.1:8000"


def fetch(method: str, url: str, data: Optional[dict] = None) -> dict:
    req = Request(url, method=method)
    if data is not None:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    ok = True
    # 1) GET OHLCV
    print("1. GET /ohlcv?symbol=RELIANCE&days=90 ...")
    try:
        ohlcv_res = fetch("GET", f"{BASE}/ohlcv?symbol=RELIANCE&days=90")
    except (URLError, HTTPError) as e:
        print(f"   FAIL: {e}")
        print("   Make sure the API is running: .venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000")
        return 1
    ohlcv = ohlcv_res.get("ohlcv") or []
    if not ohlcv:
        print("   FAIL: no ohlcv data")
        return 1
    print(f"   OK: {len(ohlcv)} bars, symbol={ohlcv_res.get('symbol', '?')}")

    # 2) POST Enrich
    print("2. POST /enrich (with ohlcv) ...")
    try:
        enrich_res = fetch("POST", f"{BASE}/enrich?debug=1", {"ohlcv": ohlcv, "symbol": ohlcv_res.get("symbol")})
    except (URLError, HTTPError) as e:
        print(f"   FAIL: {e}")
        return 1
    if isinstance(enrich_res, str):
        try:
            enrich_res = json.loads(enrich_res)
        except json.JSONDecodeError:
            print(f"   FAIL: enrich response is string (not JSON): {enrich_res[:200]!r}")
            return 1
    if not isinstance(enrich_res, dict):
        print(f"   FAIL: enrich response type {type(enrich_res)}")
        return 1
    indicators = enrich_res.get("indicators") or {}
    with_values = sum(1 for v in indicators.values() if v is not None)
    total = len(indicators)
    if total == 0:
        print("   FAIL: no indicators key in response")
        ok = False
    elif with_values == 0:
        print(f"   FAIL: indicators present ({total} keys) but all values are null")
        ok = False
    else:
        print(f"   OK: indicators {with_values}/{total} with values")
        for k, v in list(indicators.items())[:5]:
            if v is not None:
                print(f"      {k}: {v}")
    if "_debug" in enrich_res:
        d = enrich_res["_debug"]
        print(f"   _debug: request_rows={d.get('request_rows')}, df_rows={d.get('df_rows')}, close_sample={d.get('close_sample')}")

    # 3) GET Sentiment
    print("3. GET /sentiment?symbol=RELIANCE&lookback_days=7 ...")
    try:
        sent_res = fetch("GET", f"{BASE}/sentiment?symbol=RELIANCE&lookback_days=7")
    except (URLError, HTTPError) as e:
        print(f"   FAIL: {e}")
        return 1
    print(f"   OK: score={sent_res.get('score')}, count={sent_res.get('article_count', '?')}")

    # 4) Health / app
    print("4. GET /app ...")
    try:
        urlopen(Request(f"{BASE}/app", method="GET"), timeout=5)
    except Exception as e:
        print(f"   WARN: {e}")
    else:
        print("   OK")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
