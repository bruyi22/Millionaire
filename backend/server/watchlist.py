"""
FASE 3 - Gestion de la watchlist (lista de tickers a vigilar).

Persistida en un simple archivo data/watchlist.json. Sin base de datos.
"""

from __future__ import annotations

import json
from pathlib import Path

WATCHLIST_FILE = Path(__file__).resolve().parent.parent / "data" / "watchlist.json"


def _ensure_file() -> None:
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not WATCHLIST_FILE.exists():
        WATCHLIST_FILE.write_text(json.dumps(["KO"], indent=2), encoding="utf-8")


def _save(tickers: list[str]) -> None:
    WATCHLIST_FILE.write_text(json.dumps(tickers, indent=2), encoding="utf-8")


def get_watchlist() -> list[str]:
    _ensure_file()
    return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))


def add_ticker(ticker: str) -> list[str]:
    t = ticker.upper().strip()
    tickers = get_watchlist()
    if t and t not in tickers:
        tickers.append(t)
        _save(tickers)
    return tickers


def remove_ticker(ticker: str) -> list[str]:
    t = ticker.upper().strip()
    tickers = [x for x in get_watchlist() if x != t]
    _save(tickers)
    return tickers
