"""Resolve user symbol to exchange-specific (e.g. RELIANCE -> RELIANCE.NS)."""

import csv
from pathlib import Path
from typing import Optional

_symbol_map: Optional[dict[str, tuple[str, str]]] = None  # symbol -> (yahoo_symbol, company_name)


def load_symbol_map(symbols_path: str) -> dict[str, tuple[str, str]]:
    """Load symbols.csv: symbol, yahoo_symbol, company_name, exchange. Returns symbol -> (yahoo_symbol, company_name)."""
    path = Path(symbols_path)
    if not path.is_absolute():
        base = Path(__file__).resolve().parent.parent.parent
        path = base / symbols_path
    out: dict[str, tuple[str, str]] = {}
    if not path.exists():
        return out
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            sym = (row.get("symbol") or "").strip().upper()
            yahoo = (row.get("yahoo_symbol") or "").strip()
            company = (row.get("company_name") or "").strip()
            if sym and yahoo:
                out[sym] = (yahoo, company)
    return out


def resolve_symbol(
    symbol: str,
    symbols_path: str,
    default_suffix: str = ".NS",
) -> tuple[str, Optional[str]]:
    """
    Return (yahoo_symbol, company_name).
    If symbol is already like RELIANCE.NS, return as-is (or lookup by base).
    Otherwise look up in symbols_path; if not found, append default_suffix.
    """
    global _symbol_map
    symbol = symbol.strip().upper()
    if not symbol:
        return f"RELIANCE{default_suffix}", None  # fallback
    base = symbol.split(".")[0] if "." in symbol else symbol
    if _symbol_map is None:
        _symbol_map = load_symbol_map(symbols_path)
    if _symbol_map is None:
        _symbol_map = {}
    if base in _symbol_map:
        yahoo, company = _symbol_map[base]
        return yahoo, company or None
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol, None
    return f"{symbol}{default_suffix}", None


def set_symbol_map(mapping: dict[str, tuple[str, str]]) -> None:
    """Inject symbol map (e.g. for tests)."""
    global _symbol_map
    _symbol_map = mapping
