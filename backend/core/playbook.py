"""
FASE 9 - Playbook INTRADÍA (momentum, velas de 5 min).

Codifica el checklist clásico de day-trading de momentum (el mismo que funcionó
en SOFI): VWAP, EMA 9/20/50 intradía, MACD y RSI intradía, volumen relativo y
ruptura/reclaim de niveles. Devuelve un veredicto accionable PENSADO PARA MIRAR
EN VIVO desde el panel mientras vigilas el ticker (no es alerta automática: el
atraso del feed lo haría perseguir el movimiento).

Reglas que replica (todas deterministas, GRATIS, sin IA):
  - Esperar CONFIRMACIÓN: no comprar antes de la ruptura.
  - No perseguir velas verdes: si RSI extremo + precio estirado sobre VWAP, esperar.
  - Reclaim: tras pullback, comprar al recuperar VWAP + EMAs con MACD girando.
  - Respetar soportes/resistencias (los niveles intradía).

NO ejecuta órdenes.
"""

from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from core.analysis import macd, rsi
from core.intraday import intraday_data

MARKET_TZ = ZoneInfo("America/New_York")

# Umbrales del playbook (afinables tras ver en vivo).
RSI_OVERBOUGHT = 78        # por encima => no perseguir, espera pullback
RSI_HEALTHY_MAX = 72       # zona "saludable" para una entrada de momentum
STRONG_REL_VOLUME = 1.3    # volumen de la vela vs media de la sesión
EXTENDED_VWAP_PCT = 1.5    # precio a >1.5% sobre VWAP = estirado


def _ema(series: pd.Series, span: int) -> float:
    val = series.ewm(span=span, adjust=False).mean().iloc[-1]
    return round(float(val), 2) if not math.isnan(val) else None


def _vwap(df: pd.DataFrame) -> float:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["volume"].replace(0, pd.NA)
    cum_v = df["volume"].cumsum()
    cum_tpv = (tp * df["volume"]).cumsum()
    val = (cum_tpv / cum_v).iloc[-1]
    return round(float(val), 2) if cum_v.iloc[-1] else None


def _nearest(levels: dict, price: float, keys, above: bool):
    """Nivel más cercano por encima (above=True) o por debajo del precio."""
    cand = [(k, levels.get(k)) for k in keys]
    cand = [(k, v) for k, v in cand if v and ((v > price) if above else (v < price))]
    if not cand:
        return None
    name, val = (min if above else max)(cand, key=lambda kv: kv[1])
    pretty = {"r1": "R1", "r2": "R2", "pivot": "Pivot", "s1": "S1", "s2": "S2",
              "day_high": "máx. del día", "day_low": "mín. del día"}.get(name, name)
    return {"level": pretty, "price": val, "distance_pct": round((val - price) / price * 100, 2)}


def intraday_playbook(ticker: str) -> dict:
    """Veredicto intradía de momentum a partir de velas de 5 min. Solo lectura."""
    data = intraday_data(ticker, interval="5m")
    candles = data["candles"]
    levels = data["levels"]
    price = data["current_price"]
    if len(candles) < 10:
        raise ValueError(f"Pocas velas intradía para '{ticker}' (mercado sin abrir aún).")

    df = pd.DataFrame(candles)
    close = df["close"]

    vwap = _vwap(df)
    ema9, ema20, ema50 = _ema(close, 9), _ema(close, 20), _ema(close, 50)
    _, _, macd_hist = macd(close)
    hist = round(float(macd_hist.iloc[-1]), 4)
    hist_prev = float(macd_hist.iloc[-3]) if len(macd_hist) >= 3 else hist
    rsi_val = round(float(rsi(close).iloc[-1]), 1)

    avg_vol = float(df["volume"][:-1].mean()) or 1.0
    rel_vol = round(float(df["volume"].iloc[-1]) / avg_vol, 2) if avg_vol else 0.0

    # --- Posiciones / señales (el checklist alcista de ChatGPT) ---
    above_vwap = vwap is not None and price > vwap
    above_ema9 = ema9 is not None and price > ema9
    stack_full = None not in (ema9, ema20, ema50) and ema9 > ema20 > ema50
    stack_partial = ema9 is not None and ema20 is not None and ema9 > ema20
    macd_bull = hist > 0
    macd_turning = hist > hist_prev
    healthy_rsi = rsi_val < RSI_HEALTHY_MAX
    overbought = rsi_val >= RSI_OVERBOUGHT
    strong_vol = rel_vol >= STRONG_REL_VOLUME
    extended = above_vwap and vwap and (price - vwap) / vwap * 100 > EXTENDED_VWAP_PCT

    # Reclaim: en las últimas 6 velas el precio pinchó BAJO el VWAP y ahora volvió.
    dipped = vwap is not None and float(df["low"].tail(6).min()) < vwap
    reclaim = above_vwap and above_ema9 and dipped and macd_turning

    resistance = _nearest(levels, price, ("r1", "r2", "pivot", "day_high"), above=True)
    support = _nearest(levels, price, ("s1", "s2", "pivot", "day_low"), above=False)

    checklist = [
        {"label": "Precio sobre VWAP", "ok": bool(above_vwap)},
        {"label": "Precio sobre EMA 9", "ok": bool(above_ema9)},
        {"label": "EMAs apiladas alcista (9>20>50)", "ok": bool(stack_full)},
        {"label": "MACD alcista (intradía)", "ok": bool(macd_bull)},
        {"label": f"RSI saludable (<{RSI_HEALTHY_MAX})", "ok": bool(healthy_rsi)},
        {"label": f"Volumen fuerte (x{STRONG_REL_VOLUME}+)", "ok": bool(strong_vol)},
    ]

    # --- Veredicto (árbol determinista fiel al método) ---
    just_broke = resistance is None and above_vwap  # nada por encima => sobre máximos
    broke_res = resistance is not None and price >= resistance["price"]

    stop_ref = None  # se fija solo en los veredictos de COMPRAR

    if not above_vwap:
        action, head = "SIN SETUP", "⚪ Sin ventaja alcista"
        detail = ("Precio BAJO el VWAP. No hay setup de compra; espera a que "
                  "recupere el VWAP. Sesgo bajista mientras siga debajo.")
    elif overbought or extended:
        action, head = "NO PERSEGUIR", "🟠 No persigas"
        detail = (f"RSI {rsi_val} / precio estirado sobre VWAP. Comprar aquí es "
                  "perseguir la vela. Espera un pullback a VWAP o EMA 9 y un reclaim.")
    elif reclaim and macd_bull and healthy_rsi:
        stop_ref = ema9 or vwap
        action, head = "COMPRAR (reclaim)", "🟢 Reclaim sobre VWAP+EMAs"
        detail = (f"Recuperó VWAP/EMAs con MACD girando. Entrada de momentum; "
                  f"invalida si pierde `${stop_ref}` (VWAP/EMA 9).")
    elif (broke_res or just_broke) and strong_vol and macd_bull and not overbought:
        nivel = "el máximo del día" if just_broke else f"{resistance['level']} (${resistance['price']})"
        stop_ref = vwap or ema9
        action, head = "COMPRAR (ruptura)", "🟢 Ruptura confirmada"
        detail = (f"Rompió {nivel} con volumen y MACD alcista. Entrada de "
                  f"momentum; invalida si pierde `${stop_ref}` (VWAP).")
    elif above_vwap and (stack_partial or macd_bull) and resistance is not None:
        action, head = "ESPERAR RUPTURA", "🟡 Esperar confirmación"
        detail = (f"Alcista pero aún bajo {resistance['level']} (`${resistance['price']}`, "
                  f"{resistance['distance_pct']:+}%). NO compres todavía: espera la "
                  "ruptura con volumen, o un reclaim de VWAP tras pullback.")
    else:
        action, head = "SIN SETUP", "⚪ Señales mixtas"
        detail = "Sobre VWAP pero sin confluencia clara. Espera ruptura o reclaim."

    # Plan accionable SOLO cuando hay compra: entrada/stop/objetivo concretos.
    # (Para los demás veredictos no hay orden que dar, así que plan = None.)
    plan = None
    if stop_ref is not None:
        target = resistance["price"] if resistance else None
        plan = {
            "entry": price,                 # entra cerca de aquí (límite, no perseguir)
            "stop": round(float(stop_ref), 2),
            "target": target,               # None = sin nivel claro arriba (deja correr)
        }

    last_time = candles[-1]["time"]
    return {
        "ticker": ticker,
        "current_price": price,
        "candle_time": last_time,          # hora de la última vela (frescura)
        "et_now": datetime.now(MARKET_TZ).strftime("%Y-%m-%d %H:%M %Z"),
        "indicators": {
            "vwap": vwap, "ema9": ema9, "ema20": ema20, "ema50": ema50,
            "macd_hist": hist, "rsi": rsi_val, "rel_volume": rel_vol,
        },
        "levels": {"resistance": resistance, "support": support},
        "checklist": checklist,
        "verdict": {"action": action, "headline": head, "detail": detail, "plan": plan},
        "note": "Solo soporte de decisión intradía · mira el precio en vivo de tu bróker · tú decides y ejecutas",
    }
