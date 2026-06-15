"""
FASE 7 - Contrato recomendado (scorer de la cadena de opciones).

El Paso 3 (señal) dice la DIRECCIÓN (CALL/PUT). Este módulo ELIGE el mejor
contrato para esa dirección, en vez de solo mostrar la cadena entera.

Puntúa cada contrato (0-100) por: ajuste de delta, spread, liquidez (OI+volumen),
IV relativa a la cadena, y movimiento al break-even. Descalifica los peligrosos
(spread enorme, ilíquidos, far OTM "lotería") y clasifica en:
  - Recomendado (mejor equilibrio)
  - Agresivo  (más OTM: más barato, más apalancado, más riesgo)
  - Evitar    (descalificados, con motivo)

Earnings: APROXIMADO con yfinance.calendar (data gratis poco fiable). Si caen
antes del vencimiento, penaliza y marca bandera.

NO ejecuta ordenes ni dice "compra". Solo describe y clasifica.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import median

import yfinance as yf

from core.options import option_chain_analysis
from core.signal import decision_signal

# Pesos del scorer (suman 100).
W_DELTA = 30
W_SPREAD = 25
W_LIQ = 25
W_IV = 10
W_BE = 10

EARNINGS_PENALTY = 12  # puntos que resta si hay earnings antes del vencimiento


def _delta_fit(delta: float) -> float:
    d = abs(delta)
    if 0.35 <= d <= 0.60:
        return 1.0
    if 0.25 <= d < 0.35 or 0.60 < d <= 0.70:
        return 0.7
    if 0.20 <= d < 0.25 or 0.70 < d <= 0.80:
        return 0.4
    return 0.1


def _spread_score(s: float) -> float:
    if s <= 5:
        return 1.0
    if s <= 10:
        return 0.8
    if s <= 15:
        return 0.6
    if s <= 25:
        return 0.3
    return 0.1


def _liquidity_score(oi: int, vol: int) -> float:
    oi_s = min(oi / 1000, 1.0)
    vol_s = min(vol / 200, 1.0)
    return 0.6 * oi_s + 0.4 * vol_s


def _iv_score(iv: float, median_iv: float) -> float:
    if median_iv <= 0:
        return 0.6
    ratio = iv / median_iv
    if ratio <= 0.8:
        return 1.0
    if ratio <= 1.0:
        return 0.8
    if ratio <= 1.2:
        return 0.6
    if ratio <= 1.5:
        return 0.4
    return 0.2


def _em_score(be_em_ratio: float | None) -> float:
    """Puntúa el movimiento al break-even RELATIVO al movimiento esperado (IV).

    ratio = |mov. al break-even| / mov. esperado del vencimiento.
    < 1 = el break-even cae dentro de lo que el mercado espera (favorable).
    > 1 = el contrato pide más movimiento del que el mercado cotiza (caro).
    Si no hay expected move fiable, valor neutro (0.5) para no premiar ni penalizar.
    """
    if be_em_ratio is None:
        return 0.5
    r = be_em_ratio
    if r <= 0.5:
        return 1.0
    if r <= 0.75:
        return 0.85
    if r <= 1.0:
        return 0.6
    if r <= 1.3:
        return 0.3
    return 0.1


def _disqualifiers(c: dict) -> list[str]:
    reasons: list[str] = []
    if c["spread_pct"] > 30:
        reasons.append(f"spread {c['spread_pct']}% (te come la prima)")
    if c["open_interest"] < 50 and c["volume"] < 10:
        reasons.append("ilíquido (OI<50 y volumen<10)")
    if abs(c["delta"]) < 0.15:
        reasons.append(f"far OTM Δ{c['delta']} (lotería)")
    return reasons


def _reasons(c: dict, comp: dict) -> list[str]:
    r: list[str] = []
    d = abs(c["delta"])
    if 0.35 <= d <= 0.60:
        r.append("delta ideal")
    elif d < 0.35:
        r.append(f"algo OTM (Δ{c['delta']})")
    else:
        r.append(f"algo ITM (Δ{c['delta']})")
    if c["spread_pct"] <= 10:
        r.append("spread ajustado")
    elif c["spread_pct"] <= 20:
        r.append("spread medio")
    else:
        r.append("spread ancho")
    if comp["liq"] >= 0.6:
        r.append("buena liquidez")
    elif comp["liq"] >= 0.3:
        r.append("liquidez media")
    else:
        r.append("liquidez floja")
    if comp["iv"] <= 0.4:
        r.append("IV elevada")
    # Break-even relativo al movimiento esperado (lo más decisivo para opciones).
    ratio = c.get("be_em_ratio")
    if ratio is not None:
        if ratio <= 0.75:
            r.append(f"BE dentro del mov. esperado ({ratio}x)")
        elif ratio <= 1.0:
            r.append(f"BE al borde del mov. esperado ({ratio}x)")
        else:
            r.append(f"BE pide más que el mov. esperado ({ratio}x)")
    return r


def _earnings_before(tk: yf.Ticker, dte: int | None) -> tuple[bool, str | None]:
    """¿Hay earnings entre hoy y el vencimiento? Aproximado (data poco fiable)."""
    if not dte or dte <= 0:
        return False, None
    try:
        cal = tk.calendar
    except Exception:  # noqa: BLE001
        return False, None

    dates: list = []
    try:
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed:
                dates = list(ed) if isinstance(ed, (list, tuple)) else [ed]
        elif cal is not None and "Earnings Date" in getattr(cal, "index", []):
            dates = [cal.loc["Earnings Date"][0]]
    except Exception:  # noqa: BLE001
        dates = []

    today = date.today()
    horizon = today + timedelta(days=dte)
    for d in dates:
        dd = d.date() if hasattr(d, "date") else d
        try:
            if today <= dd <= horizon:
                return True, str(dd)
        except TypeError:
            continue
    return False, None


def recommend_contracts(
    ticker: str, direction: str | None = None, expiry: str | None = None
) -> dict:
    """Elige el mejor contrato para la dirección de la señal. GRATIS, sin IA."""
    ticker = ticker.upper().strip()

    # Dirección: explícita o derivada de la señal del Paso 3.
    signal_state = None
    if direction is None:
        sig = decision_signal(ticker)
        direction = sig["direction"]
        signal_state = sig["signal"]
    direction = direction.upper()

    chain = option_chain_analysis(ticker, expiry=expiry, n_strikes=10)
    side = chain["calls"] if direction == "CALL" else chain["puts"] if direction == "PUT" else []

    base = {
        "ticker": ticker,
        "direction": direction,
        "signal_state": signal_state,
        "expiry": chain["expiry"],
        "dte": chain["dte"],
        "underlying_price": chain["underlying_price"],
        "available_expiries": chain["available_expiries"],
        "expected_move": chain.get("expected_move"),
        "expected_move_pct": chain.get("expected_move_pct"),
        "em_method": chain.get("em_method"),
    }

    if direction not in ("CALL", "PUT") or not side:
        return {
            **base,
            "recommended": None,
            "aggressive": None,
            "avoid": [],
            "scored": [],
            "earnings_warning": False,
            "earnings_date": None,
            "note": (
                "Sin dirección clara (la señal es NO OPERAR/NEUTRAL): no se "
                "recomienda contrato."
                if direction not in ("CALL", "PUT")
                else f"No hay contratos {direction} cerca del dinero para {chain['expiry']}."
            ),
        }

    earnings_warning, earnings_date = _earnings_before(
        yf.Ticker(ticker), chain["dte"]
    )
    median_iv = median([c["iv"] for c in side]) if side else 0.0

    viable: list[dict] = []
    avoid: list[dict] = []
    scored: list[dict] = []

    for c in side:
        disq = _disqualifiers(c)
        comp = {
            "delta": _delta_fit(c["delta"]),
            "spread": _spread_score(c["spread_pct"]),
            "liq": _liquidity_score(c["open_interest"], c["volume"]),
            "iv": _iv_score(c["iv"], median_iv),
            "be": _em_score(c.get("be_em_ratio")),
        }
        score = (
            W_DELTA * comp["delta"]
            + W_SPREAD * comp["spread"]
            + W_LIQ * comp["liq"]
            + W_IV * comp["iv"]
            + W_BE * comp["be"]
        )
        if earnings_warning:
            score -= EARNINGS_PENALTY
        score = round(max(0, score))

        row = {
            "strike": c["strike"],
            "type": c["type"],
            "delta": c["delta"],
            "spread_pct": c["spread_pct"],
            "open_interest": c["open_interest"],
            "volume": c["volume"],
            "iv": c["iv"],
            "mid": c["mid"],
            "break_even": c["break_even"],
            "break_even_move_pct": c["break_even_move_pct"],
            "be_em_ratio": c.get("be_em_ratio"),
            "theta": c["theta"],
            "score": score,
        }

        if disq:
            row["category"] = "Evitar"
            row["reasons"] = disq
            avoid.append(row)
        else:
            row["category"] = "Viable"
            row["reasons"] = _reasons(c, comp)
            if earnings_warning:
                row["reasons"].append(f"earnings {earnings_date} antes del venc.")
            viable.append(row)
        scored.append(row)

    viable.sort(key=lambda r: r["score"], reverse=True)

    recommended = viable[0] if viable else None
    aggressive = None
    if recommended:
        rec_d = abs(recommended["delta"])
        for r in viable[1:]:
            if 0.20 <= abs(r["delta"]) < rec_d:
                aggressive = r
                break

    if recommended:
        recommended = {**recommended, "category": "Recomendado"}
        note = f"Recomendado: {direction} strike {recommended['strike']} (score {recommended['score']})."
    else:
        note = "Ningún contrato pasa los filtros de liquidez/spread. Mejor no operar opciones aquí."
    if aggressive:
        aggressive = {**aggressive, "category": "Agresivo"}

    return {
        **base,
        "recommended": recommended,
        "aggressive": aggressive,
        "avoid": avoid,
        "scored": sorted(scored, key=lambda r: r["strike"]),
        "earnings_warning": earnings_warning,
        "earnings_date": earnings_date,
        "note": note,
    }
