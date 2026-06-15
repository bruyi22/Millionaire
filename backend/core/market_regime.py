"""
FASE 7 - Market Regime Score.

Responde, UNA sola vez (no por ticker), la pregunta previa a todo:
    "¿El mercado permite operar hoy o no?"

Combina senales GRATIS (yfinance) en un score de -100 a +100:
  - QQQ : direccion del tech (lo que mas pesa en opciones).
  - SPY : direccion del mercado amplio.
  - VIX : miedo/volatilidad (con veto: VIX extremo => NO OPERAR).
  - Semis (NVDA + SMH): el sector que lidera el apetito de riesgo.

Cada componente se evalua por:
  - precio vs VWAP del dia (sobre/bajo el precio promedio ponderado por volumen),
  - precio vs apertura del dia (% de cambio en la sesion).

Resultado: ALCISTA / BAJISTA / MIXTO / NO OPERAR.

NO ejecuta ordenes. Solo describe el contexto de mercado.
"""

from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import yfinance as yf

MARKET_TZ = ZoneInfo("America/New_York")

# Pesos de cada componente (suman 100). Como cada componente vota en [-1, +1],
# la suma ponderada cae naturalmente en [-100, +100].
WEIGHTS = {"qqq": 30.0, "spy": 25.0, "vix": 25.0, "semis": 20.0}

# Umbrales del veredicto final.
BULL_THRESHOLD = 40.0
BEAR_THRESHOLD = -40.0

# VIX: por encima de este nivel, el mercado es demasiado nervioso => NO OPERAR.
VIX_VETO = 28.0


def _safe(value) -> float:
    try:
        v = float(value)
        return 0.0 if math.isnan(v) else v
    except (TypeError, ValueError):
        return 0.0


def is_market_open(now: datetime | None = None) -> bool:
    """NYSE: Lun-Vie 9:30-16:00 ET. No maneja feriados."""
    now = now or datetime.now(MARKET_TZ)
    if now.weekday() >= 5:
        return False
    open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_t <= now <= close_t


def _index_snapshot(ticker: str) -> dict:
    """Foto intradia de un indice/ETF: precio, apertura, VWAP y direcciones.

    Si hoy no hay sesion, cae a los ultimos dias disponibles (la ultima vela
    valida sigue siendo util como referencia de cierre).
    """
    tk = yf.Ticker(ticker)
    intra = tk.history(period="1d", interval="5m")
    if intra.empty:
        intra = tk.history(period="5d", interval="5m")
    if intra.empty:
        raise ValueError(f"Sin datos intradia para '{ticker}'.")

    intra = intra[intra["Close"].notna()]
    if intra.empty:
        raise ValueError(f"Sin velas validas para '{ticker}'.")

    day_open = _safe(intra["Open"].iloc[0])
    current = _safe(intra["Close"].iloc[-1])

    # VWAP = sum(precio_tipico * volumen) / sum(volumen).
    typical = (intra["High"] + intra["Low"] + intra["Close"]) / 3.0
    vol = intra["Volume"].fillna(0.0)
    total_vol = float(vol.sum())
    if total_vol > 0:
        vwap = float((typical * vol).sum() / total_vol)
    else:
        # Sin volumen (p.ej. el indice ^VIX) => VWAP no aplica; usamos la media.
        vwap = float(intra["Close"].mean())

    pct_from_open = (current - day_open) / day_open * 100 if day_open else 0.0

    return {
        "ticker": ticker,
        "price": round(current, 2),
        "day_open": round(day_open, 2),
        "vwap": round(vwap, 2),
        "pct_from_open": round(pct_from_open, 2),
        "above_vwap": current > vwap,
    }


def _direction_component(snap: dict) -> float:
    """Vota en {-1, 0, +1} combinando VWAP y cambio desde la apertura.

    +0.5 si esta sobre VWAP (sino -0.5); +0.5 si sube en el dia (sino -0.5).
    Si ambos coinciden => +-1 (senal clara); si discrepan => 0 (mixto).
    """
    score = 0.5 if snap["above_vwap"] else -0.5
    score += 0.5 if snap["pct_from_open"] > 0 else -0.5
    return score


def _vix_component(vix_snap: dict) -> tuple[float, str]:
    """VIX bajo = apetito de riesgo (bueno para CALL); VIX alto = miedo.

    Devuelve (voto en [-1, +1], etiqueta legible).
    """
    level = vix_snap["price"]
    if level < 16:
        return 1.0, "calmo"
    if level < 20:
        return 0.3, "normal"
    if level < 24:
        return -0.3, "elevado"
    if level < VIX_VETO:
        return -0.7, "alto"
    return -1.0, "extremo"


def market_regime() -> dict:
    """Calcula el Market Regime Score. GRATIS (sin IA)."""
    open_now = is_market_open()

    components: dict[str, dict] = {}
    errors: dict[str, str] = {}

    def _grab(key: str, ticker: str):
        try:
            components[key] = _index_snapshot(ticker)
        except Exception as exc:  # noqa: BLE001
            errors[key] = str(exc)

    _grab("spy", "SPY")
    _grab("qqq", "QQQ")
    _grab("vix", "^VIX")
    _grab("nvda", "NVDA")
    _grab("smh", "SMH")

    breakdown: list[dict] = []
    weighted = 0.0
    used_weight = 0.0

    # --- QQQ ---
    if "qqq" in components:
        c = _direction_component(components["qqq"])
        weighted += WEIGHTS["qqq"] * c
        used_weight += WEIGHTS["qqq"]
        breakdown.append(_bd("QQQ (tech)", WEIGHTS["qqq"], c, components["qqq"]))

    # --- SPY ---
    if "spy" in components:
        c = _direction_component(components["spy"])
        weighted += WEIGHTS["spy"] * c
        used_weight += WEIGHTS["spy"]
        breakdown.append(_bd("SPY (mercado)", WEIGHTS["spy"], c, components["spy"]))

    # --- VIX ---
    vix_label = None
    if "vix" in components:
        c, vix_label = _vix_component(components["vix"])
        weighted += WEIGHTS["vix"] * c
        used_weight += WEIGHTS["vix"]
        bd = _bd(f"VIX ({vix_label})", WEIGHTS["vix"], c, components["vix"])
        bd["detail"] = f"nivel {components['vix']['price']}"
        breakdown.append(bd)

    # --- Semis: promedio de NVDA y SMH ---
    semis = [components[k] for k in ("nvda", "smh") if k in components]
    if semis:
        c = sum(_direction_component(s) for s in semis) / len(semis)
        weighted += WEIGHTS["semis"] * c
        used_weight += WEIGHTS["semis"]
        names = " + ".join(s["ticker"] for s in semis)
        bd = {
            "name": f"Semis ({names})",
            "weight": WEIGHTS["semis"],
            "vote": round(c, 2),
            "contribution": round(WEIGHTS["semis"] * c, 1),
            "detail": ", ".join(
                f"{s['ticker']} {'+' if s['pct_from_open'] >= 0 else ''}{s['pct_from_open']}%"
                for s in semis
            ),
        }
        breakdown.append(bd)

    # Reescalamos por el peso realmente usado, para que un fallo puntual de un
    # componente no aplaste el score (sigue en rango -100..+100).
    score = round(weighted / used_weight * 100, 1) if used_weight else 0.0

    # --- Veredicto + vetos ---
    veto_reason = None
    if not open_now:
        veto_reason = "Mercado cerrado (fuera de 9:30-16:00 ET)."
    elif "vix" in components and components["vix"]["price"] >= VIX_VETO:
        veto_reason = f"VIX extremo ({components['vix']['price']}): volatilidad peligrosa."

    if veto_reason:
        regime = "NO OPERAR"
    elif score >= BULL_THRESHOLD:
        regime = "ALCISTA"
    elif score <= BEAR_THRESHOLD:
        regime = "BAJISTA"
    else:
        regime = "MIXTO"

    return {
        "regime": regime,
        "score": score,
        "market_open": open_now,
        "veto_reason": veto_reason,
        "vix_level": components["vix"]["price"] if "vix" in components else None,
        "vix_label": vix_label,
        "summary": _summary(regime, score),
        "breakdown": breakdown,
        "errors": errors or None,
        "ts": datetime.now(MARKET_TZ).isoformat(timespec="seconds"),
    }


def _bd(name: str, weight: float, vote: float, snap: dict) -> dict:
    """Fila del desglose para un indice direccional."""
    return {
        "name": name,
        "weight": weight,
        "vote": round(vote, 2),
        "contribution": round(weight * vote, 1),
        "detail": (
            f"${snap['price']} · {'+' if snap['pct_from_open'] >= 0 else ''}"
            f"{snap['pct_from_open']}% · {'sobre' if snap['above_vwap'] else 'bajo'} VWAP"
        ),
    }


def _summary(regime: str, score: float) -> str:
    if regime == "NO OPERAR":
        return "No hay ventaja: el contexto no permite operar con seguridad."
    if regime == "ALCISTA":
        return f"Viento a favor para CALL (score {score:+.0f}). Sesgo comprador."
    if regime == "BAJISTA":
        return f"Viento a favor para PUT (score {score:+.0f}). Sesgo vendedor."
    return f"Mercado indeciso (score {score:+.0f}). Operar solo setups muy claros."
