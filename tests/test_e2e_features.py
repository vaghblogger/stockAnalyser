"""
End-to-end tests for re-architecture features.
Run: .venv/bin/python -m pytest tests/test_e2e_features.py -v
Or:  .venv/bin/python tests/test_e2e_features.py
"""
import os
import tempfile
from pathlib import Path

import pytest

# Use a temp cache dir so we don't pollute real data
os.environ.pop("CACHE_DIR", None)


@pytest.fixture(scope="module")
def app():
    """Create app with temp cache dir for isolation."""
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CACHE_DIR"] = str(Path(tmp) / "cache")
        from src.api.main import app as fastapi_app
        yield fastapi_app


@pytest.fixture
def client(app):
    """Use TestClient as context manager so lifespan runs and app.state is set."""
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


# --- Health & core ---
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ohlcv_single(client):
    r = client.get("/ohlcv?symbol=RELIANCE&days=30")
    assert r.status_code == 200
    data = r.json()
    assert "ohlcv" in data
    assert "symbol" in data
    assert isinstance(data["ohlcv"], list)


# --- Data / Universe ---
def test_data_universe_list(client):
    r = client.get("/api/data/universe")
    assert r.status_code == 200
    data = r.json()
    assert "symbols" in data
    assert "count" in data
    assert data["count"] >= 0


def test_data_add_symbol(client):
    r = client.post("/api/data/universe", json={"symbol": "TESTSTOCK", "yahoo_symbol": "TESTSTOCK.NS", "company_name": "Test"})
    assert r.status_code == 200
    assert r.json().get("ok") is True
    r2 = client.delete("/api/data/universe/TESTSTOCK")
    assert r2.status_code == 200


def test_data_get_and_update_universe_symbol(client):
    client.post("/api/data/universe", json={"symbol": "EDITSTOCK", "yahoo_symbol": "EDITSTOCK.NS", "company_name": "Edit Co"})
    r = client.get("/api/data/universe/item/EDITSTOCK")
    assert r.status_code == 200
    data = r.json()
    assert data["symbol"] == "EDITSTOCK"
    assert data["company_name"] == "Edit Co"
    r2 = client.put("/api/data/universe/EDITSTOCK", json={"company_name": "Edit Company Ltd"})
    assert r2.status_code == 200
    updated = r2.json()
    assert updated.get("company_name") == "Edit Company Ltd"
    assert updated.get("symbol") == "EDITSTOCK"
    client.delete("/api/data/universe/EDITSTOCK")


# --- Dashboard views ---
def test_dashboard_views_list(client):
    r = client.get("/api/dashboard/views")
    assert r.status_code == 200
    data = r.json()
    assert "views" in data
    assert "count" in data


def test_dashboard_views_create_and_update(client):
    r = client.post("/api/dashboard/views", json={"name": "Test View", "columns_config": [{"key": "close", "visible": True, "order": 0}]})
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    view_id = data["id"]
    r2 = client.put(f"/api/dashboard/views/{view_id}", json={"columns_config": [{"key": "close", "visible": True, "order": 0}, {"key": "rsi", "visible": True, "order": 1}]})
    assert r2.status_code == 200
    r3 = client.delete(f"/api/dashboard/views/{view_id}")
    assert r3.status_code == 200


# --- Strategies ---
def test_strategies_crud(client):
    r = client.get("/api/strategies")
    assert r.status_code == 200
    assert "strategies" in r.json()
    create = client.post("/api/strategies", json={"name": "E2E Strategy", "description": "Test", "strategy_type": "rule_based", "params": {"rsi_buy_below": 30, "rsi_sell_above": 70}, "is_global_default": False})
    assert create.status_code == 200
    sid = create.json()["id"]
    r2 = client.get(f"/api/strategies/{sid}")
    assert r2.status_code == 200
    client.delete(f"/api/strategies/{sid}")


def test_strategies_set_default(client):
    create = client.post("/api/strategies", json={"name": "Default Strategy", "params": {}, "is_global_default": False})
    assert create.status_code == 200
    sid = create.json()["id"]
    r = client.post(f"/api/strategies/{sid}/set-default")
    assert r.status_code == 200
    client.delete(f"/api/strategies/{sid}")


# --- Backtest (single & multi-symbol, strategy_id) ---
def test_backtest_single(client):
    r = client.post("/backtest", json={"symbol": "RELIANCE", "start": "2023-01-01", "end": "2023-06-01", "lookback_days": 30, "hold_days": 5, "step_days": 5})
    assert r.status_code == 200
    data = r.json()
    assert "metrics" in data
    assert "rows" in data
    assert "strategy" in data
    m = data.get("metrics", {})
    assert "portfolio" in m or "by_signal" in m


def test_backtest_with_strategy_id(client):
    create = client.post("/api/strategies", json={"name": "BT Strategy", "params": {"rsi_buy_below": 28}, "is_global_default": False})
    assert create.status_code == 200
    sid = create.json()["id"]
    r = client.post("/backtest", json={"symbol": "RELIANCE", "start": "2023-01-01", "end": "2023-06-01", "strategy_id": sid})
    assert r.status_code == 200
    assert r.json().get("strategy", {}).get("name") == "BT Strategy"
    client.delete(f"/api/strategies/{sid}")


def test_backtest_multi_symbol(client):
    r = client.post("/backtest", json={"symbols": ["RELIANCE", "TCS"], "start": "2023-01-01", "end": "2023-06-01", "lookback_days": 30})
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    assert "by_symbol" in data
    assert "RELIANCE" in data.get("by_symbol", {}) or "TCS" in data.get("by_symbol", {})


# --- Paper trading ---
def test_paper_portfolios_crud(client):
    r = client.get("/api/paper/portfolios")
    assert r.status_code == 200
    assert "portfolios" in r.json()
    create = client.post("/api/paper/portfolios", json={"name": "E2E Paper", "initial_capital": 1000000, "currency": "INR"})
    assert create.status_code == 200
    pid = create.json()["id"]
    r2 = client.get(f"/api/paper/portfolios/{pid}")
    assert r2.status_code == 200
    assert r2.json()["portfolio"]["name"] == "E2E Paper"
    client.post(f"/api/paper/portfolios/{pid}/positions", json={"symbol": "RELIANCE", "strategy_ids": []})
    r3 = client.get(f"/api/paper/portfolios/{pid}/positions")
    assert r3.status_code == 200
    client.delete(f"/api/paper/portfolios/{pid}")


def test_paper_run(client):
    create = client.post("/api/paper/portfolios", json={"name": "Run Test", "initial_capital": 1000000})
    assert create.status_code == 200
    pid = create.json()["id"]
    client.post(f"/api/paper/portfolios/{pid}/positions", json={"symbol": "RELIANCE", "strategy_ids": []})
    r = client.post(f"/api/paper/portfolios/{pid}/run", json={})
    # May return 200 with ok:true or 503 if provider issue
    assert r.status_code in (200, 503)
    if r.status_code == 200 and r.json().get("ok"):
        snap = client.get(f"/api/paper/portfolios/{pid}/snapshots")
        assert snap.status_code == 200
    client.delete(f"/api/paper/portfolios/{pid}")


# --- Dashboard (stocks list) ---
def test_dashboard_get(client):
    r = client.get("/dashboard?lookback_days=90")
    assert r.status_code == 200
    data = r.json()
    assert "stocks" in data
    assert "count" in data


# --- Enrich (for Analysis flow) ---
def test_enrich(client):
    ohlcv_r = client.get("/ohlcv?symbol=RELIANCE&days=60")
    assert ohlcv_r.status_code == 200
    ohlcv = ohlcv_r.json()
    r = client.post("/enrich", json={"ohlcv": ohlcv["ohlcv"], "symbol": ohlcv["symbol"]})
    assert r.status_code == 200
    data = r.json()
    assert "indicators" in data or "ohlcv_with_indicators" in data


# --- Data seed ---
def test_data_seed(client):
    r = client.post("/api/data/seed", json={"lookback_days": 5})
    assert r.status_code == 200
    data = r.json()
    assert "ok" in data
    assert "success" in data
    assert "failed" in data


# --- Static / SPA ---
def test_app_index(client):
    r = client.get("/app")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert b"<!DOCTYPE html>" in r.content or b"<html" in r.content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
