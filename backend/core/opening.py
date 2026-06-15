"""
FASE 7 - Modulo de apertura (9:30-10:00 ET).

"Lo mas importante": la primera media hora define el dia. Este modulo aplica
DISCIPLINA en vez de dar senales prematuras:

  - 9:30-9:45  => OBSERVAR. Solo informa. NO operar todavia.
  - 9:45-10:00 => CONFIRMANDO. Ya hay rango; vigila ruptura + VWAP + volumen.
  - >=10:00    => DECISION. Veredicto de apertura: CALL / PUT / NO OPERAR.

Detecta, en orden cronologico, los patrones de apertura (hueco, ruptura con
volumen, ruptura falsa, sacudida/shakeout, perdida/recuperacion de VWAP) y arma
un "relato del dia".

Decisiones de alcance v1 (data gratis):
  - Sesgo premarket APROXIMADO con el hueco (apertura vs cierre previo).
  - Volumen "elevado" = volumen de la vela vs promedio de la sesion.
  - Fuera de horario: usa la ULTIMA sesion disponible (live=False).

NO ejecuta ordenes. Solo describe la apertura.
"""

from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

MARKET_TZ = ZoneInfo("America/New_York")

OPEN_MIN = 9 * 60 + 30   # 09:30 -> 570 minutos desde medianoche
CONFIRM_MIN = 9 * 60 + 45  # 09:45 -> 585
DECISION_MIN = 10 * 60   # 10:00 -> 600
CLOSE_MIN = 16 * 60      # 16:00 -> 960

VOL_ELEVATED = 1.3       # vela "con volumen" si >= 1.3x el promedio de la sesion
GAP_THRESHOLD = 0.3      # % minimo para considerar hueco significativo


def _safe(value) -> float:
    try:
        v = float(value)
        return 0.0 if math.isnan(v) else v
    except (TypeError, ValueError):
        return 0.0


def _session_candles(ticker: str) -> tuple[list[dict], object, bool]:
    """Velas 5m de la sesion mas reciente (regular 9:30-16:00 ET) + VWAP acumulado.

    Devuelve (candles, session_date, live). Cada vela trae open/high/low/close,
    volumen, vol_ratio (vs promedio de la sesion), vwap acumulado y `mins`
    (minutos desde medianoche ET).
    """
    tk = yf.Ticker(ticker)
    intra = tk.history(period="1d", interval="5m", prepost=False)
    if intra.empty:
        intra = tk.history(period="5d", interval="5m", prepost=False)
    intra = intra[intra["Close"].notna()] if not intra.empty else intra
    if intra.empty:
        raise ValueError(f"Sin datos intradia para '{ticker}'.")

    # Aseguramos zona horaria de Nueva York.
    idx = intra.index
    if idx.tz is None:
        intra.index = idx.tz_localize("UTC").tz_convert(MARKET_TZ)
    else:
        intra.index = idx.tz_convert(MARKET_TZ)

    ts = intra.index
    session_date = ts[-1].date()
    mins = ts.hour * 60 + ts.minute
    mask = (ts.date == session_date) & (mins >= OPEN_MIN) & (mins <= CLOSE_MIN)
    session = intra[mask]
    if session.empty:
        raise ValueError(f"Sin velas de sesion regular para '{ticker}'.")

    vols = [_safe(v) for v in session["Volume"]]
    avg_vol = (sum(vols) / len(vols)) if vols else 0.0

    candles: list[dict] = []
    cum_tpv = 0.0  # suma(precio_tipico * volumen)
    cum_vol = 0.0
    cum_close = 0.0  # respaldo si no hay volumen
    for i, (t, row) in enumerate(session.iterrows()):
        o, h, l, c = (
            _safe(row["Open"]),
            _safe(row["High"]),
            _safe(row["Low"]),
            _safe(row["Close"]),
        )
        vol = _safe(row["Volume"])
        typical = (h + l + c) / 3.0
        cum_tpv += typical * vol
        cum_vol += vol
        cum_close += c
        vwap = (cum_tpv / cum_vol) if cum_vol > 0 else (cum_close / (i + 1))
        candles.append(
            {
                "time": t.strftime("%H:%M"),
                "mins": int(t.hour * 60 + t.minute),
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "volume": int(vol),
                "vol_ratio": round(vol / avg_vol, 2) if avg_vol > 0 else 0.0,
                "vwap": round(vwap, 2),
            }
        )

    live = session_date == datetime.now(MARKET_TZ).date()
    return candles, session_date, live


def _prev_close(ticker: str, session_date) -> float:
    """Cierre diario de la sesion ANTERIOR a session_date (para el hueco)."""
    daily = yf.Ticker(ticker).history(period="1mo", interval="1d")
    daily = daily[daily["Close"].notna()]
    prev = 0.0
    for t, row in daily.iterrows():
        d = t.date() if hasattr(t, "date") else t
        if d < session_date:
            prev = _safe(row["Close"])
    return prev


def opening_analysis(ticker: str) -> dict:
    """Analisis de la apertura (9:30-10:00 ET). GRATIS, sin IA."""
    ticker = ticker.upper().strip()
    candles, session_date, live = _session_candles(ticker)

    opening = [c for c in candles if c["mins"] < DECISION_MIN]  # 9:30-10:00
    n_open = len(opening)
    or_candles = [c for c in opening if c["mins"] < CONFIRM_MIN]  # 9:30-9:45

    last = opening[-1] if opening else candles[-1]
    current_price = last["close"]
    vwap = last["vwap"]
    day_open = opening[0]["open"] if opening else candles[0]["open"]

    prev_close = _prev_close(ticker, session_date)
    gap_pct = round((day_open - prev_close) / prev_close * 100, 2) if prev_close else 0.0
    if gap_pct >= GAP_THRESHOLD:
        premarket_bias = "alcista"
    elif gap_pct <= -GAP_THRESHOLD:
        premarket_bias = "bajista"
    else:
        premarket_bias = "neutral"

    # --- Fase segun cuantas velas de apertura tenemos ---
    if n_open < 3:
        phase, phase_label = "OBSERVAR", "Observar (antes de 9:45)"
    elif n_open < 6:
        phase, phase_label = "CONFIRMANDO", "Confirmando (9:45-10:00)"
    else:
        phase, phase_label = "DECISION", "Decisión (10:00)"

    # --- Rango de apertura (si ya hay al menos una vela) ---
    or_high = max((c["high"] for c in or_candles), default=last["high"])
    or_low = min((c["low"] for c in or_candles), default=last["low"])

    # --- Construccion del relato ---
    events: list[str] = []
    if gap_pct >= GAP_THRESHOLD:
        events.append(f"Hueco alcista {gap_pct:+.1f}%")
    elif gap_pct <= -GAP_THRESHOLD:
        events.append(f"Hueco bajista {gap_pct:+.1f}%")
    else:
        events.append("Apertura plana")

    broke_high = broke_low = False
    false_high = shakeout = False
    breakout_volume = False
    prev_side: str | None = None

    # Solo escaneamos a partir de 9:45 (tras formar el rango).
    for c in (x for x in opening if x["mins"] >= CONFIRM_MIN):
        v = c["vwap"]
        side = "above" if c["close"] >= v else "below"
        if prev_side == "below" and side == "above":
            events.append("recuperación de VWAP")
        elif prev_side == "above" and side == "below":
            events.append("pérdida de VWAP")
        prev_side = side

        if not broke_high and c["high"] > or_high:
            if c["close"] > or_high:
                broke_high = True
                breakout_volume = c["vol_ratio"] >= VOL_ELEVATED
                events.append(
                    "ruptura del máximo con volumen"
                    if breakout_volume
                    else "ruptura del máximo (volumen flojo)"
                )
            elif not false_high:
                false_high = True
                events.append("ruptura falsa al alza")

        if not broke_low and c["low"] < or_low:
            if c["close"] < or_low:
                broke_low = True
                breakout_volume = c["vol_ratio"] >= VOL_ELEVATED
                events.append(
                    "ruptura del mínimo con volumen"
                    if breakout_volume
                    else "ruptura del mínimo (volumen flojo)"
                )
            elif not shakeout:
                shakeout = True
                events.append("sacudida bajo el mínimo (shakeout)")

    above_vwap = current_price >= vwap

    # --- Sesgo y veredicto ---
    if broke_high and not broke_low:
        bias = "CALL"
    elif broke_low and not broke_high:
        bias = "PUT"
    else:
        bias = "NEUTRAL"

    if phase == "OBSERVAR":
        signal = "OBSERVAR"
        confidence = "baja"
        note = "Antes de 9:45 solo se observa. La 1ª vela informa, no decide."
    elif phase == "CONFIRMANDO":
        signal = "ESPERAR"
        confidence = "media" if bias != "NEUTRAL" else "baja"
        note = (
            "Rango de apertura formado. Esperando confirmación cerca de las 10:00."
        )
    else:  # DECISION
        if bias == "CALL" and above_vwap:
            signal = "CALL"
        elif bias == "PUT" and not above_vwap:
            signal = "PUT"
        else:
            signal = "NO OPERAR"
        if signal == "NO OPERAR":
            confidence = "baja"
        elif breakout_volume:
            confidence = "alta"
        else:
            confidence = "media"
        note = {
            "CALL": "Ruptura alcista confirmada sobre el rango y VWAP.",
            "PUT": "Ruptura bajista confirmada bajo el rango y VWAP.",
            "NO OPERAR": "Sin ruptura limpia: la apertura no da ventaja. Mejor esperar.",
        }[signal]

    # Cierre del relato.
    closing = {
        "CALL": "→ CALL válido",
        "PUT": "→ PUT válido",
        "NO OPERAR": "→ sin ventaja, NO operar",
        "ESPERAR": "→ esperar confirmación",
        "OBSERVAR": "→ solo observar",
    }[signal]
    narrative = " → ".join(events) + " " + closing

    return {
        "ticker": ticker,
        "session_date": str(session_date),
        "live": live,
        "interval": "5m",
        "phase": phase,
        "phase_label": phase_label,
        "opening_range": {"high": round(or_high, 2), "low": round(or_low, 2)},
        "vwap": vwap,
        "current_price": current_price,
        "above_vwap": above_vwap,
        "gap_pct": gap_pct,
        "premarket_bias": premarket_bias,
        "bias": bias,
        "signal": signal,
        "confidence": confidence,
        "events": events,
        "narrative": narrative,
        "note": note,
        "candles_in_opening": n_open,
    }
