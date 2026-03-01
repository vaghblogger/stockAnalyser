"""App DB (SQLite): dashboard views, strategies, symbol universe, paper portfolios."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


def get_app_db_path(cache_dir: str) -> Path:
    """App DB lives next to cache dir: e.g. data/cache -> data/app.db."""
    base = Path(cache_dir).resolve().parent
    base.mkdir(parents=True, exist_ok=True)
    return base / "app.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dashboard_views (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    user_id TEXT,
    columns_config TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    strategy_type TEXT NOT NULL DEFAULT 'rule_based',
    params TEXT NOT NULL,
    is_global_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symbol_universe (
    symbol TEXT PRIMARY KEY,
    yahoo_symbol TEXT,
    company_name TEXT,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_portfolios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    initial_capital REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_portfolio_positions (
    id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    strategy_ids TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(portfolio_id, symbol),
    FOREIGN KEY (portfolio_id) REFERENCES paper_portfolios(id)
);

CREATE TABLE IF NOT EXISTS paper_equity_snapshots (
    id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    date TEXT NOT NULL,
    equity REAL NOT NULL,
    cash REAL NOT NULL,
    positions TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(portfolio_id, date),
    FOREIGN KEY (portfolio_id) REFERENCES paper_portfolios(id)
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_portfolio ON paper_portfolio_positions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_paper_snapshots_portfolio_date ON paper_equity_snapshots(portfolio_id, date);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id TEXT PRIMARY KEY,
    strategy_id TEXT,
    strategy_name TEXT NOT NULL,
    strategy_description TEXT,
    symbols TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    params TEXT NOT NULL,
    metrics TEXT NOT NULL,
    rows TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_created_at ON backtest_runs(created_at DESC);
"""


def init_app_db(cache_dir: str) -> None:
    """Create app.db and tables if they don't exist."""
    path = get_app_db_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (1, ?)",
            (datetime.utcnow().isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()


def _conn(cache_dir: str) -> sqlite3.Connection:
    return sqlite3.connect(str(get_app_db_path(cache_dir)))


def _now() -> str:
    return datetime.utcnow().isoformat()


# --- Dashboard views ---


def list_dashboard_views(cache_dir: str, user_id: Optional[str] = None) -> list[dict]:
    conn = _conn(cache_dir)
    try:
        if user_id is not None:
            cur = conn.execute(
                "SELECT id, name, user_id, columns_config, created_at, updated_at FROM dashboard_views WHERE user_id IS NULL OR user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            )
        else:
            cur = conn.execute(
                "SELECT id, name, user_id, columns_config, created_at, updated_at FROM dashboard_views ORDER BY updated_at DESC"
            )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "user_id": r[2],
                "columns_config": json.loads(r[3]) if r[3] else [],
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_dashboard_view(cache_dir: str, view_id: str) -> Optional[dict]:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute(
            "SELECT id, name, user_id, columns_config, created_at, updated_at FROM dashboard_views WHERE id = ?",
            (view_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "name": r[1],
            "user_id": r[2],
            "columns_config": json.loads(r[3]) if r[3] else [],
            "created_at": r[4],
            "updated_at": r[5],
        }
    finally:
        conn.close()


def create_dashboard_view(
    cache_dir: str,
    name: str,
    columns_config: list[dict],
    view_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict:
    vid = view_id or str(uuid4())
    now = _now()
    conn = _conn(cache_dir)
    try:
        conn.execute(
            "INSERT INTO dashboard_views (id, name, user_id, columns_config, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (vid, name, user_id, json.dumps(columns_config), now, now),
        )
        conn.commit()
        return {
            "id": vid,
            "name": name,
            "user_id": user_id,
            "columns_config": columns_config,
            "created_at": now,
            "updated_at": now,
        }
    finally:
        conn.close()


def update_dashboard_view(
    cache_dir: str, view_id: str, name: Optional[str] = None, columns_config: Optional[list[dict]] = None
) -> Optional[dict]:
    conn = _conn(cache_dir)
    try:
        existing = get_dashboard_view(cache_dir, view_id)
        if not existing:
            return None
        now = _now()
        name = name if name is not None else existing["name"]
        columns_config = columns_config if columns_config is not None else existing["columns_config"]
        conn.execute(
            "UPDATE dashboard_views SET name = ?, columns_config = ?, updated_at = ? WHERE id = ?",
            (name, json.dumps(columns_config), now, view_id),
        )
        conn.commit()
        return {**existing, "name": name, "columns_config": columns_config, "updated_at": now}
    finally:
        conn.close()


def delete_dashboard_view(cache_dir: str, view_id: str) -> bool:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute("DELETE FROM dashboard_views WHERE id = ?", (view_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Strategies ---


def list_strategies(cache_dir: str) -> list[dict]:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute(
            "SELECT id, name, description, strategy_type, params, is_global_default, created_at, updated_at FROM strategies ORDER BY is_global_default DESC, name"
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "strategy_type": r[3],
                "params": json.loads(r[4]) if r[4] else {},
                "is_global_default": bool(r[5]),
                "created_at": r[6],
                "updated_at": r[7],
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_strategy(cache_dir: str, strategy_id: str) -> Optional[dict]:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute(
            "SELECT id, name, description, strategy_type, params, is_global_default, created_at, updated_at FROM strategies WHERE id = ?",
            (strategy_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "name": r[1],
            "description": r[2],
            "strategy_type": r[3],
            "params": json.loads(r[4]) if r[4] else {},
            "is_global_default": bool(r[5]),
            "created_at": r[6],
            "updated_at": r[7],
        }
    finally:
        conn.close()


def get_global_default_strategy(cache_dir: str) -> Optional[dict]:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute(
            "SELECT id, name, description, strategy_type, params, is_global_default, created_at, updated_at FROM strategies WHERE is_global_default = 1 LIMIT 1"
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "name": r[1],
            "description": r[2],
            "strategy_type": r[3],
            "params": json.loads(r[4]) if r[4] else {},
            "is_global_default": True,
            "created_at": r[6],
            "updated_at": r[7],
        }
    finally:
        conn.close()


def create_strategy(
    cache_dir: str,
    name: str,
    strategy_type: str = "rule_based",
    params: Optional[dict] = None,
    description: str = "",
    is_global_default: bool = False,
    strategy_id: Optional[str] = None,
) -> dict:
    sid = strategy_id or str(uuid4())
    now = _now()
    params = params or {}
    conn = _conn(cache_dir)
    try:
        if is_global_default:
            conn.execute("UPDATE strategies SET is_global_default = 0 WHERE 1=1")
        conn.execute(
            "INSERT INTO strategies (id, name, description, strategy_type, params, is_global_default, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, name, description, strategy_type, json.dumps(params), 1 if is_global_default else 0, now, now),
        )
        conn.commit()
        return {
            "id": sid,
            "name": name,
            "description": description,
            "strategy_type": strategy_type,
            "params": params,
            "is_global_default": is_global_default,
            "created_at": now,
            "updated_at": now,
        }
    finally:
        conn.close()


def update_strategy(
    cache_dir: str,
    strategy_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    params: Optional[dict] = None,
) -> Optional[dict]:
    existing = get_strategy(cache_dir, strategy_id)
    if not existing:
        return None
    now = _now()
    name = name if name is not None else existing["name"]
    description = description if description is not None else existing["description"]
    params = params if params is not None else existing["params"]
    conn = _conn(cache_dir)
    try:
        conn.execute(
            "UPDATE strategies SET name = ?, description = ?, params = ?, updated_at = ? WHERE id = ?",
            (name, description, json.dumps(params), now, strategy_id),
        )
        conn.commit()
        return {**existing, "name": name, "description": description, "params": params, "updated_at": now}
    finally:
        conn.close()


def set_global_default_strategy(cache_dir: str, strategy_id: str) -> Optional[dict]:
    s = get_strategy(cache_dir, strategy_id)
    if not s:
        return None
    conn = _conn(cache_dir)
    try:
        conn.execute("UPDATE strategies SET is_global_default = 0 WHERE 1=1")
        conn.execute("UPDATE strategies SET is_global_default = 1, updated_at = ? WHERE id = ?", (_now(), strategy_id))
        conn.commit()
        return get_strategy(cache_dir, strategy_id)
    finally:
        conn.close()


def delete_strategy(cache_dir: str, strategy_id: str) -> bool:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Backtest runs (history) ---


def save_backtest_run(
    cache_dir: str,
    *,
    strategy_id: Optional[str] = None,
    strategy_name: str,
    strategy_description: str = "",
    symbols: list[str],
    start_date: str,
    end_date: str,
    params: dict,
    metrics: dict,
    rows: list[dict],
    run_id: Optional[str] = None,
) -> dict:
    """Persist a backtest run. Returns the saved run with id."""
    now = _now()
    rid = run_id or str(uuid4())
    conn = _conn(cache_dir)
    try:
        conn.execute(
            """INSERT INTO backtest_runs (
                id, strategy_id, strategy_name, strategy_description,
                symbols, start_date, end_date, params, metrics, rows, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rid,
                strategy_id,
                strategy_name or "Rule-based",
                strategy_description or "",
                json.dumps(symbols),
                start_date,
                end_date,
                json.dumps(params),
                json.dumps(metrics),
                json.dumps(rows),
                now,
            ),
        )
        conn.commit()
        return {
            "id": rid,
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "strategy_description": strategy_description,
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "params": params,
            "metrics": metrics,
            "rows": rows,
            "created_at": now,
        }
    finally:
        conn.close()


def list_backtest_runs(
    cache_dir: str,
    limit: int = 50,
    offset: int = 0,
    symbol: Optional[str] = None,
    strategy_id: Optional[str] = None,
) -> list[dict]:
    """List backtest runs, newest first. Optional filter by symbol (in symbols list) or strategy_id."""
    conn = _conn(cache_dir)
    try:
        if symbol or strategy_id:
            conditions = []
            args: list[Any] = []
            if strategy_id:
                conditions.append("strategy_id = ?")
                args.append(strategy_id)
            if symbol:
                conditions.append("symbols LIKE ?")
                args.append("%" + json.dumps(symbol) + "%")
            where = " AND ".join(conditions) if conditions else "1=1"
            args.extend([limit, offset])
            cur = conn.execute(
                f"""SELECT id, strategy_id, strategy_name, symbols, start_date, end_date, params, metrics, created_at
                    FROM backtest_runs WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                args,
            )
        else:
            cur = conn.execute(
                """SELECT id, strategy_id, strategy_name, symbols, start_date, end_date, params, metrics, created_at
                   FROM backtest_runs ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            )
        out = []
        for r in cur.fetchall():
            try:
                symbols_list = json.loads(r[3]) if isinstance(r[3], str) else r[3]
                params_obj = json.loads(r[6]) if isinstance(r[6], str) else r[6]
                metrics_obj = json.loads(r[7]) if isinstance(r[7], str) else r[7]
            except (json.JSONDecodeError, TypeError):
                symbols_list = []
                params_obj = {}
                metrics_obj = {}
            portfolio = (metrics_obj or {}).get("portfolio") or {}
            out.append({
                "id": r[0],
                "strategy_id": r[1],
                "strategy_name": r[2],
                "symbols": symbols_list,
                "start_date": r[4],
                "end_date": r[5],
                "params": params_obj,
                "metrics": metrics_obj,
                "portfolio": portfolio,
                "created_at": r[8],
            })
        return out
    finally:
        conn.close()


def get_backtest_run(cache_dir: str, run_id: str) -> Optional[dict]:
    """Get a single backtest run by id, with full rows."""
    conn = _conn(cache_dir)
    try:
        cur = conn.execute(
            """SELECT id, strategy_id, strategy_name, strategy_description, symbols, start_date, end_date,
                      params, metrics, rows, created_at FROM backtest_runs WHERE id = ?""",
            (run_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        symbols_list = json.loads(r[4]) if isinstance(r[4], str) else r[4]
        params_obj = json.loads(r[7]) if isinstance(r[7], str) else r[7]
        metrics_obj = json.loads(r[8]) if isinstance(r[8], str) else r[8]
        rows_list = json.loads(r[9]) if isinstance(r[9], str) else r[9]
        return {
            "id": r[0],
            "strategy_id": r[1],
            "strategy_name": r[2],
            "strategy_description": r[3],
            "symbols": symbols_list,
            "start_date": r[5],
            "end_date": r[6],
            "params": params_obj,
            "metrics": metrics_obj,
            "rows": rows_list,
            "created_at": r[10],
            "strategy": {
                "name": r[2],
                "description": r[3] or "",
            },
        }
    finally:
        conn.close()


def delete_backtest_run(cache_dir: str, run_id: str) -> bool:
    """Delete a backtest run by id."""
    conn = _conn(cache_dir)
    try:
        cur = conn.execute("DELETE FROM backtest_runs WHERE id = ?", (run_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Symbol universe ---


def list_universe_symbols(cache_dir: str) -> list[dict]:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute("SELECT symbol, yahoo_symbol, company_name, added_at FROM symbol_universe ORDER BY symbol")
        return [
            {"symbol": r[0], "yahoo_symbol": r[1], "company_name": r[2], "added_at": r[3]}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def add_universe_symbol(
    cache_dir: str, symbol: str, yahoo_symbol: Optional[str] = None, company_name: Optional[str] = None
) -> dict:
    now = _now()
    yahoo_symbol = yahoo_symbol or symbol
    conn = _conn(cache_dir)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO symbol_universe (symbol, yahoo_symbol, company_name, added_at) VALUES (?, ?, ?, ?)",
            (symbol.strip().upper(), yahoo_symbol, company_name or "", now),
        )
        conn.commit()
        return {"symbol": symbol.strip().upper(), "yahoo_symbol": yahoo_symbol, "company_name": company_name or "", "added_at": now}
    finally:
        conn.close()


def get_universe_symbol(cache_dir: str, symbol: str) -> Optional[dict]:
    """Return one universe symbol by symbol (primary key) or None."""
    conn = _conn(cache_dir)
    try:
        cur = conn.execute(
            "SELECT symbol, yahoo_symbol, company_name, added_at FROM symbol_universe WHERE symbol = ?",
            (symbol.strip().upper(),),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {"symbol": r[0], "yahoo_symbol": r[1], "company_name": r[2], "added_at": r[3]}
    finally:
        conn.close()


def get_universe_symbol_by_any(cache_dir: str, symbol: str) -> Optional[dict]:
    """Find a universe row by symbol (primary key), yahoo_symbol, or base part of yahoo_symbol."""
    key = (symbol or "").strip().upper()
    if not key:
        return None
    s = get_universe_symbol(cache_dir, key)
    if s:
        return s
    if not key.endswith((".NS", ".BO")):
        s = get_universe_symbol(cache_dir, key + ".NS") or get_universe_symbol(cache_dir, key + ".BO")
        if s:
            return s
    for row in list_universe_symbols(cache_dir):
        base = ((row.get("yahoo_symbol") or row.get("symbol") or "").split(".")[0] or "").strip().upper()
        if base == key or (row.get("symbol") or "").strip().upper() == key or (row.get("yahoo_symbol") or "").strip() == symbol.strip():
            return row
    return None


def update_universe_symbol(
    cache_dir: str,
    symbol: str,
    company_name: Optional[str] = None,
    yahoo_symbol: Optional[str] = None,
) -> Optional[dict]:
    """Update company_name and/or yahoo_symbol for an existing symbol. Returns updated row or None."""
    existing = get_universe_symbol(cache_dir, symbol)
    if not existing:
        return None
    name = company_name if company_name is not None else existing["company_name"]
    yahoo = yahoo_symbol if yahoo_symbol is not None else existing["yahoo_symbol"]
    conn = _conn(cache_dir)
    try:
        conn.execute(
            "UPDATE symbol_universe SET company_name = ?, yahoo_symbol = ? WHERE symbol = ?",
            (name or "", yahoo, symbol.strip().upper()),
        )
        conn.commit()
        return get_universe_symbol(cache_dir, symbol)
    except Exception:
        return None
    finally:
        conn.close()


def remove_universe_symbol(cache_dir: str, symbol: str) -> bool:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute("DELETE FROM symbol_universe WHERE symbol = ?", (symbol.strip().upper(),))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def set_universe_symbols(cache_dir: str, symbols: list[dict]) -> None:
    """Replace full universe with list of {symbol, yahoo_symbol?, company_name?}."""
    conn = _conn(cache_dir)
    try:
        conn.execute("DELETE FROM symbol_universe")
        now = _now()
        for s in symbols:
            sym = (s.get("symbol") or s.get("yahoo_symbol") or "").strip().upper()
            if not sym:
                continue
            yahoo = s.get("yahoo_symbol") or sym
            name = s.get("company_name") or ""
            conn.execute(
                "INSERT INTO symbol_universe (symbol, yahoo_symbol, company_name, added_at) VALUES (?, ?, ?, ?)",
                (sym, yahoo, name, now),
            )
        conn.commit()
    finally:
        conn.close()


# --- Paper portfolios ---


def list_paper_portfolios(cache_dir: str) -> list[dict]:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute(
            "SELECT id, name, initial_capital, currency, created_at, updated_at FROM paper_portfolios ORDER BY created_at"
        )
        return [
            {
                "id": r[0],
                "name": r[1],
                "initial_capital": r[2],
                "currency": r[3],
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def get_paper_portfolio(cache_dir: str, portfolio_id: str) -> Optional[dict]:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute(
            "SELECT id, name, initial_capital, currency, created_at, updated_at FROM paper_portfolios WHERE id = ?",
            (portfolio_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "name": r[1],
            "initial_capital": r[2],
            "currency": r[3],
            "created_at": r[4],
            "updated_at": r[5],
        }
    finally:
        conn.close()


def create_paper_portfolio(
    cache_dir: str,
    name: str,
    initial_capital: float,
    currency: str = "INR",
    portfolio_id: Optional[str] = None,
) -> dict:
    pid = portfolio_id or str(uuid4())
    now = _now()
    conn = _conn(cache_dir)
    try:
        conn.execute(
            "INSERT INTO paper_portfolios (id, name, initial_capital, currency, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (pid, name, initial_capital, currency, now, now),
        )
        conn.commit()
        return {
            "id": pid,
            "name": name,
            "initial_capital": initial_capital,
            "currency": currency,
            "created_at": now,
            "updated_at": now,
        }
    finally:
        conn.close()


def update_paper_portfolio(
    cache_dir: str, portfolio_id: str, name: Optional[str] = None, initial_capital: Optional[float] = None
) -> Optional[dict]:
    existing = get_paper_portfolio(cache_dir, portfolio_id)
    if not existing:
        return None
    now = _now()
    name = name if name is not None else existing["name"]
    initial_capital = initial_capital if initial_capital is not None else existing["initial_capital"]
    conn = _conn(cache_dir)
    try:
        conn.execute(
            "UPDATE paper_portfolios SET name = ?, initial_capital = ?, updated_at = ? WHERE id = ?",
            (name, initial_capital, now, portfolio_id),
        )
        conn.commit()
        return {**existing, "name": name, "initial_capital": initial_capital, "updated_at": now}
    finally:
        conn.close()


def delete_paper_portfolio(cache_dir: str, portfolio_id: str) -> bool:
    conn = _conn(cache_dir)
    try:
        conn.execute("DELETE FROM paper_portfolio_positions WHERE portfolio_id = ?", (portfolio_id,))
        conn.execute("DELETE FROM paper_equity_snapshots WHERE portfolio_id = ?", (portfolio_id,))
        cur = conn.execute("DELETE FROM paper_portfolios WHERE id = ?", (portfolio_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_paper_positions(cache_dir: str, portfolio_id: str) -> list[dict]:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute(
            "SELECT id, portfolio_id, symbol, strategy_ids, created_at, updated_at FROM paper_portfolio_positions WHERE portfolio_id = ? ORDER BY symbol",
            (portfolio_id,),
        )
        return [
            {
                "id": r[0],
                "portfolio_id": r[1],
                "symbol": r[2],
                "strategy_ids": json.loads(r[3]) if r[3] else [],
                "created_at": r[4],
                "updated_at": r[5],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def set_paper_positions(cache_dir: str, portfolio_id: str, positions: list[dict]) -> None:
    """Replace all positions. Each item: {symbol, strategy_ids: [id, ...]}."""
    conn = _conn(cache_dir)
    try:
        conn.execute("DELETE FROM paper_portfolio_positions WHERE portfolio_id = ?", (portfolio_id,))
        now = _now()
        for p in positions:
            pid = str(uuid4())
            symbol = (p.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            strategy_ids = p.get("strategy_ids") or []
            conn.execute(
                "INSERT INTO paper_portfolio_positions (id, portfolio_id, symbol, strategy_ids, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (pid, portfolio_id, symbol, json.dumps(strategy_ids), now, now),
            )
        conn.commit()
    finally:
        conn.close()


def add_paper_position(cache_dir: str, portfolio_id: str, symbol: str, strategy_ids: Optional[list[str]] = None) -> dict:
    pos_id = str(uuid4())
    now = _now()
    strategy_ids = strategy_ids or []
    symbol = symbol.strip().upper()
    conn = _conn(cache_dir)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO paper_portfolio_positions (id, portfolio_id, symbol, strategy_ids, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (pos_id, portfolio_id, symbol, json.dumps(strategy_ids), now, now),
        )
        conn.commit()
        return {
            "id": pos_id,
            "portfolio_id": portfolio_id,
            "symbol": symbol,
            "strategy_ids": strategy_ids,
            "created_at": now,
            "updated_at": now,
        }
    finally:
        conn.close()


def remove_paper_position(cache_dir: str, portfolio_id: str, symbol: str) -> bool:
    conn = _conn(cache_dir)
    try:
        cur = conn.execute(
            "DELETE FROM paper_portfolio_positions WHERE portfolio_id = ? AND symbol = ?",
            (portfolio_id, symbol.strip().upper()),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- Paper equity snapshots ---


def append_paper_snapshot(
    cache_dir: str,
    portfolio_id: str,
    date: str,
    equity: float,
    cash: float,
    positions: Optional[dict] = None,
) -> dict:
    sid = str(uuid4())
    now = _now()
    positions_json = json.dumps(positions) if positions is not None else None
    conn = _conn(cache_dir)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO paper_equity_snapshots (id, portfolio_id, date, equity, cash, positions, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, portfolio_id, date, equity, cash, positions_json, now),
        )
        conn.commit()
        return {
            "id": sid,
            "portfolio_id": portfolio_id,
            "date": date,
            "equity": equity,
            "cash": cash,
            "positions": positions,
            "created_at": now,
        }
    finally:
        conn.close()


def get_paper_snapshots(cache_dir: str, portfolio_id: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> list[dict]:
    conn = _conn(cache_dir)
    try:
        if from_date and to_date:
            cur = conn.execute(
                "SELECT id, portfolio_id, date, equity, cash, positions, created_at FROM paper_equity_snapshots WHERE portfolio_id = ? AND date >= ? AND date <= ? ORDER BY date",
                (portfolio_id, from_date, to_date),
            )
        elif from_date:
            cur = conn.execute(
                "SELECT id, portfolio_id, date, equity, cash, positions, created_at FROM paper_equity_snapshots WHERE portfolio_id = ? AND date >= ? ORDER BY date",
                (portfolio_id, from_date),
            )
        elif to_date:
            cur = conn.execute(
                "SELECT id, portfolio_id, date, equity, cash, positions, created_at FROM paper_equity_snapshots WHERE portfolio_id = ? AND date <= ? ORDER BY date",
                (portfolio_id, to_date),
            )
        else:
            cur = conn.execute(
                "SELECT id, portfolio_id, date, equity, cash, positions, created_at FROM paper_equity_snapshots WHERE portfolio_id = ? ORDER BY date",
                (portfolio_id,),
            )
        return [
            {
                "id": r[0],
                "portfolio_id": r[1],
                "date": r[2],
                "equity": r[3],
                "cash": r[4],
                "positions": json.loads(r[5]) if r[5] else None,
                "created_at": r[6],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
