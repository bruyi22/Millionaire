"""
FASE 6 - Datos intradia (velas) y niveles tecnicos.

Responsabilidad:
  1. Bajar velas intradia (5m por defecto) para el grafico en vivo.
  2. Calcular NIVELES exactos que sirven de disparadores:
     - Pivots clasicos (P, R1/R2, S1/S2) del dia previo.
     - Maximo / minimo / apertura del dia en curso.
     - Cierre previo.
     - SMAs (20/50/200) como niveles dinamicos.

NO ejecuta ordenes. Solo describe precios y niveles.
"""

from __future__ import annotations

import math

import yfinance as yf


def _safe(value) -> float:
    try:
        v = float(value)
        return 0.0 if math.isnan(v) else v
    except (TypeError, ValueError):
        return 0.0


def _compute_levels(intra, daily) -> dict:
    """Niveles tecnicos a partir del dia previo (pivots) y del dia en curso."""
    # Dia previo COMPLETO para los pivots (no el de hoy, que puede estar a medias).
    prev = daily.iloc[-2]
    ph, pl, pc = _safe(prev["High"]), _safe(prev["Low"]), _safe(prev["Close"])

    pivot = (ph + pl + pc) / 3
    r1 = 2 * pivot - pl
    s1 = 2 * pivot - ph
    r2 = pivot + (ph - pl)
    s2 = pivot - (ph - pl)

    # Dia en curso (a partir de las velas intradia).
    day_open = _safe(intra["Open"].iloc[0])
    day_high = _safe(intra["High"].max())
    day_low = _safe(intra["Low"].min())

    # SMAs sobre cierres diarios.
    closes = daily["Close"]
    sma20 = _safe(closes.rolling(20).mean().iloc[-1])
    sma50 = _safe(closes.rolling(50).mean().iloc[-1])
    sma200 = _safe(closes.rolling(200).mean().iloc[-1])

    return {
        "pivot": round(pivot, 2),
        "r1": round(r1, 2),
        "r2": round(r2, 2),
        "s1": round(s1, 2),
        "s2": round(s2, 2),
        "day_open": round(day_open, 2),
        "day_high": round(day_high, 2),
        "day_low": round(day_low, 2),
        "prev_close": round(pc, 2),
        "sma20": round(sma20, 2),
        "sma50": round(sma50, 2),
        "sma200": round(sma200, 2),
    }


def quick_triggers(current_price: float, levels: dict) -> dict:
    """Disparadores deterministas (sin IA, sin costo) a partir de los niveles.

    Filosofia Risk Manager: NO inventa precios ni persigue. Solo dice, con los
    niveles ya calculados, que romperia el sesgo en cada direccion:
      - CALL = nivel mas cercano POR ENCIMA del precio (romperlo = seguir subiendo).
      - PUT  = nivel mas cercano POR DEBAJO del precio (perderlo = seguir cayendo).
      - Sesgo segun el precio respecto al pivote.
    """
    ladder = [
        ("R2", levels.get("r2")),
        ("R1", levels.get("r1")),
        ("Pivot", levels.get("pivot")),
        ("S1", levels.get("s1")),
        ("S2", levels.get("s2")),
    ]
    ladder = [(name, p) for name, p in ladder if p]

    def _trig(price: float | None, name: str | None) -> dict | None:
        if price is None or not current_price:
            return None
        return {
            "level": name,
            "price": round(price, 2),
            "distance_pct": round((price - current_price) / current_price * 100, 2),
        }

    above = [(name, p) for name, p in ladder if p > current_price]
    below = [(name, p) for name, p in ladder if p < current_price]
    call = min(above, key=lambda x: x[1]) if above else None
    put = max(below, key=lambda x: x[1]) if below else None

    pivot = levels.get("pivot") or 0.0
    if current_price > pivot:
        bias = "CALL"
    elif current_price < pivot:
        bias = "PUT"
    else:
        bias = "NEUTRAL"

    return {
        "bias": bias,
        "call": _trig(call[1], call[0]) if call else None,
        "put": _trig(put[1], put[0]) if put else None,
    }


def intraday_data(ticker: str, interval: str = "5m") -> dict:
    """Velas intradia + niveles. Si hoy no hay sesion, usa la ultima disponible."""
    ticker = ticker.upper().strip()
    tk = yf.Ticker(ticker)

    intra = tk.history(period="1d", interval=interval)
    if intra.empty:
        # Mercado cerrado / sin datos hoy: caemos a los ultimos dias disponibles.
        intra = tk.history(period="5d", interval=interval)
    if intra.empty:
        raise ValueError(
            f"No hay datos intradia para '{ticker}'. Revisa el simbolo."
        )

    daily = tk.history(period="1y", interval="1d")
    # Descartamos velas diarias parciales/vacias (NaN) para no envenenar las SMAs
    # ni tomar un cierre 0 como nivel.
    daily = daily[daily["Close"].notna()]
    if len(daily) < 2:
        raise ValueError(f"No hay suficiente historico diario para '{ticker}'.")

    candles = [
        {
            "time": idx.strftime("%Y-%m-%d %H:%M"),
            "open": round(_safe(row["Open"]), 2),
            "high": round(_safe(row["High"]), 2),
            "low": round(_safe(row["Low"]), 2),
            "close": round(_safe(row["Close"]), 2),
            "volume": int(_safe(row["Volume"])),
        }
        for idx, row in intra.iterrows()
    ]

    levels = _compute_levels(intra, daily)
    current_price = candles[-1]["close"] if candles else 0.0

    return {
        "ticker": ticker,
        "interval": interval,
        "current_price": current_price,
        "candles": candles,
        "levels": levels,
        "triggers": quick_triggers(current_price, levels),
    }


def candle_summary(data: dict, n: int = 6) -> str:
    """Resumen en texto de las ultimas n velas, para alimentar a la IA."""
    candles = data["candles"][-n:]
    lines = []
    for c in candles:
        cuerpo = "alcista" if c["close"] >= c["open"] else "bajista"
        lines.append(
            f"  {c['time']}: O{c['open']} H{c['high']} L{c['low']} C{c['close']} "
            f"({cuerpo}, vol {c['volume']})"
        )
    return "\n".join(lines)
