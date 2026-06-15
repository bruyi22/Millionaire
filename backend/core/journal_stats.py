"""
PASO 7 - Estadisticas del diario de decisiones.

Lee el diario (server/journal.py) y calcula metricas de aprendizaje SOLO POR
CONTEO (sin dolares): win-rate, rachas, y desgloses por ticker y por hora del
dia. 100% DETERMINISTA y GRATIS (sin IA, sin yfinance). Solo lectura: no toca
el diario ni ejecuta ordenes.

El usuario eligio "solo conteo" (sin P/L en dolares) y desgloses por ticker +
por hora. El win-rate se basa en el `outcome` que el usuario marca a mano:
- acierto / fallo  -> operaciones CERRADAS (cuentan para win-rate y rachas)
- en_curso         -> abiertas (no cuentan)
- neutra           -> cerradas sin ganador claro (no cuentan para win-rate)
"""

from __future__ import annotations

from datetime import datetime, timezone

from server import journal

WIN = "acierto"
LOSS = "fallo"
OPEN = "en_curso"
NEUTRAL = "neutra"


def _win_rate(wins: int, losses: int) -> float | None:
    """Win-rate en % sobre operaciones decididas (acierto+fallo). None si no hay."""
    decided = wins + losses
    if decided == 0:
        return None
    return round(wins / decided * 100, 1)


def _hour_of(ts: str) -> int | None:
    """Hora del dia (0-23) en la zona del sello ISO. None si no se puede leer."""
    try:
        return datetime.fromisoformat(ts).hour
    except (ValueError, TypeError):
        return None


def _streaks(closed_chrono: list[str]) -> dict:
    """Rachas a partir de los resultados cerrados en orden cronologico.

    `closed_chrono` = lista de outcomes (solo WIN/LOSS) del mas antiguo al mas
    reciente. Devuelve la racha ACTUAL (al final) y las mejores/peores historicas.
    """
    best_win = 0
    worst_loss = 0
    run_type: str | None = None
    run_len = 0
    for o in closed_chrono:
        if o == run_type:
            run_len += 1
        else:
            run_type = o
            run_len = 1
        if o == WIN:
            best_win = max(best_win, run_len)
        elif o == LOSS:
            worst_loss = max(worst_loss, run_len)

    current = {"type": run_type, "count": run_len if run_type else 0}
    return {
        "current": current,
        "best_win_streak": best_win,
        "worst_loss_streak": worst_loss,
    }


def _bucket() -> dict:
    """Acumulador vacio para un grupo (ticker u hora)."""
    return {"total": 0, "wins": 0, "losses": 0, "neutral": 0, "open": 0}


def _finalize(group: dict) -> dict:
    """Anade win_rate a un acumulador."""
    group["win_rate"] = _win_rate(group["wins"], group["losses"])
    return group


def journal_stats() -> dict:
    """Estadisticas del diario por conteo. Solo lectura, GRATIS, no ejecuta."""
    entries = journal.get_journal()  # recientes primero

    total = len(entries)
    wins = losses = neutral = open_ = 0
    by_ticker: dict[str, dict] = {}
    by_hour: dict[int, dict] = {}

    for e in entries:
        outcome = e.get("outcome", OPEN)
        ticker = (e.get("ticker") or "?").upper()
        hour = _hour_of(e.get("ts", ""))

        tg = by_ticker.setdefault(ticker, _bucket())
        tg["total"] += 1
        hg = by_hour.setdefault(hour, _bucket()) if hour is not None else None
        if hg is not None:
            hg["total"] += 1

        if outcome == WIN:
            wins += 1
            tg["wins"] += 1
            if hg is not None:
                hg["wins"] += 1
        elif outcome == LOSS:
            losses += 1
            tg["losses"] += 1
            if hg is not None:
                hg["losses"] += 1
        elif outcome == NEUTRAL:
            neutral += 1
            tg["neutral"] += 1
            if hg is not None:
                hg["neutral"] += 1
        else:  # en_curso
            open_ += 1
            tg["open"] += 1
            if hg is not None:
                hg["open"] += 1

    # Rachas: necesito los cerrados (WIN/LOSS) del mas antiguo al mas reciente.
    closed_chrono = [
        e.get("outcome")
        for e in sorted(entries, key=lambda x: x.get("ts", ""))
        if e.get("outcome") in (WIN, LOSS)
    ]
    streaks = _streaks(closed_chrono)

    ticker_rows = sorted(
        (_finalize({"ticker": t, **g}) for t, g in by_ticker.items()),
        key=lambda r: (r["wins"] + r["losses"], r["total"]),
        reverse=True,
    )
    hour_rows = sorted(
        (
            _finalize({"hour": h, "label": f"{h:02d}:00", **g})
            for h, g in by_hour.items()
        ),
        key=lambda r: r["hour"],
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": total,
        "open": open_,
        "closed": wins + losses,
        "wins": wins,
        "losses": losses,
        "neutral": neutral,
        "win_rate": _win_rate(wins, losses),
        "streak": streaks["current"],
        "best_win_streak": streaks["best_win_streak"],
        "worst_loss_streak": streaks["worst_loss_streak"],
        "by_ticker": ticker_rows,
        "by_hour": hour_rows,
    }
