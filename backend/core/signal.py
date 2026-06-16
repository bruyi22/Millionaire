"""
FASE 7 - Señal estructurada CALL / PUT / NO OPERAR (motor de confluencias).

Filosofía rectora: "hay ventaja estadística o no hay ventaja". NO dice "compra";
dice si el conjunto de factores se alinea lo suficiente como para que exista una
ventaja, y si no, devuelve NO OPERAR.

100% DETERMINISTA y GRATIS (sin IA). Fusiona piezas ya existentes:
  - Análisis diario (tendencia, RSI, MACD, ATR, volumen).
  - Régimen de mercado (Paso 1).
  - Apertura 9:30-10:00 (Paso 2): VWAP + sesgo de apertura.
  - Niveles/pivots intradía.

Cada factor VOTA (con peso) por CALL o PUT. El acuerdo entre factores define la
confianza. Los niveles operativos (entrada/stop/targets) salen de los pivots y
del ATR, NO se inventan. El contrato aquí va LIGERO (el detalle es el Paso 4).

NO ejecuta ordenes.
"""

from __future__ import annotations

from datetime import datetime

from core.analysis import analyze_ticker
from core.intraday import intraday_data
from core.market_regime import MARKET_TZ, market_regime
from core.opening import opening_analysis

# Umbrales del veredicto. Subidos (jun-2026) para priorizar CERTEZA sobre cantidad:
# menos señales, pero cada una con mayoría real de factores y recompensa que de
# verdad compensa el theta/spread de las opciones.
MIN_AGREEMENT = 0.50   # <0.50 => no hay mayoría clara (casi moneda al aire) => NO OPERAR
MIN_CONFIDENCE = 55    # confianza mínima para dar señal (corta las "tibias")
MIN_RR = 1.5           # objetivo >= 1.5x el riesgo; por debajo el premio no paga el riesgo

# Proximidad de la ENTRADA al precio actual, medida en múltiplos de ATR.
# Operar una entrada que está a >1 ATR del precio = "perseguir" un movimiento ya
# extendido: pagas el recorrido que ya pasó y queda menos pólvora hacia el target.
# (Ej. real: dispara "rompe R1 17.02" con precio 16.58 → 0.44 de distancia; si el
#  ATR ronda 0.40, eso es ~1.1 ATR = demasiado lejos para entrar persiguiendo.)
MAX_ENTRY_ATR = 1.0    # por encima => veto: entrada demasiado lejos


def _proximity(price: float, entry: float, atr: float) -> dict:
    """Distancia precio→entrada en % y en múltiplos de ATR, con etiqueta y factor.

    `factor` (0-1) escala la confianza: 1.0 si la entrada está pegada al precio,
    cae a medida que se aleja. `state` es el semáforo para la UI/alerta.
    """
    dist_abs = abs(entry - price)
    dist_pct = round((entry - price) / price * 100, 2) if price else 0.0
    dist_atr = round(dist_abs / atr, 2) if atr > 0 else 0.0

    if dist_atr <= 0.3:
        state, label, factor = "pegado", "🟢 pegado (operable ya)", 1.0
    elif dist_atr <= 0.6:
        state, label, factor = "cerca", "🟡 algo lejos (espera el pullback)", 0.85
    elif dist_atr <= MAX_ENTRY_ATR:
        state, label, factor = "lejos", "🟠 lejos (poca pólvora restante)", 0.6
    else:
        state, label, factor = "extendido", "🔴 demasiado lejos (perseguir)", 0.3

    return {
        "entry_distance_pct": dist_pct,
        "entry_distance_atr": dist_atr,
        "proximity_state": state,
        "proximity_label": label,
        "proximity_factor": factor,
    }


def _session_window(now: datetime | None = None) -> dict:
    """Calidad de la VENTANA HORARIA de la sesión (hora de Nueva York).

    Estadística operativa probada: el rango de apertura (9:30-11:00) y la última
    hora (15:00-16:00) concentran volumen, dirección y seguimiento; el MEDIODÍA
    (11:30-14:00) suele ser 'chop' de bajo volumen con rupturas falsas. Este
    factor (0-1) escala la confianza sin vetar: el usuario decide igual.

    `factor` multiplica la confianza; `state` es el semáforo para la UI.
    Fuera de horario devuelve neutro (1.0): el veto de régimen ya cubre eso.
    """
    now = now or datetime.now(MARKET_TZ)
    mins = now.hour * 60 + now.minute  # minutos desde medianoche ET
    OPEN, CLOSE = 9 * 60 + 30, 16 * 60

    if mins < OPEN or mins >= CLOSE:
        state, label, factor = "cerrado", "fuera de sesión", 1.0
    elif mins < 11 * 60:           # 9:30-11:00
        state, label, factor = "apertura", "🟢 apertura (mayor edge)", 1.0
    elif mins < 11 * 60 + 30:      # 11:00-11:30
        state, label, factor = "media-manana", "🟡 media mañana (transición)", 0.92
    elif mins < 14 * 60:           # 11:30-14:00
        state, label, factor = "mediodia", "🔴 mediodía (chop, rupturas falsas)", 0.75
    elif mins < 15 * 60:           # 14:00-15:00
        state, label, factor = "media-tarde", "🟡 media tarde (recuperando)", 0.9
    else:                          # 15:00-16:00
        state, label, factor = "cierre", "🟢 última hora (mayor edge)", 1.0

    return {
        "session_state": state,
        "session_label": label,
        "session_factor": factor,
        "et_time": now.strftime("%H:%M"),
    }


def _overextension(rsi: float, direction: str) -> dict:
    """Penaliza ENTRAR EN AGOTAMIENTO: comprar un CALL con RSI ya muy alto (o un
    PUT con RSI muy bajo) es subirse a un movimiento maduro al que le queda poca
    pólvora y mucho riesgo de reversión.

    `factor` (0-1) escala la confianza sin vetar (degrada, como proximidad/hora).
    Solo castiga el extremo a FAVOR de la señal; un RSI alto en un PUT no penaliza
    (ahí el agotamiento juega a tu favor).
    """
    if direction == "CALL":
        if rsi >= 80:
            return {"overext_state": "agotado", "overext_label": f"🔴 RSI {rsi} (sobrecompra extrema)", "overext_factor": 0.6}
        if rsi >= 75:
            return {"overext_state": "estirado", "overext_label": f"🟡 RSI {rsi} (sobrecompra)", "overext_factor": 0.8}
    elif direction == "PUT":
        if rsi <= 20:
            return {"overext_state": "agotado", "overext_label": f"🔴 RSI {rsi} (sobreventa extrema)", "overext_factor": 0.6}
        if rsi <= 25:
            return {"overext_state": "estirado", "overext_label": f"🟡 RSI {rsi} (sobreventa)", "overext_factor": 0.8}
    return {"overext_state": "ok", "overext_label": f"🟢 RSI {rsi} (sin extremo)", "overext_factor": 1.0}


def _round(v, n=2):
    try:
        return round(float(v), n)
    except (TypeError, ValueError):
        return None


def _levels_above(levels: dict, price: float, keys) -> list[float]:
    vals = [levels.get(k) for k in keys]
    return sorted(v for v in vals if v and v > price)


def _levels_below(levels: dict, price: float, keys) -> list[float]:
    vals = [levels.get(k) for k in keys]
    return sorted((v for v in vals if v and v < price), reverse=True)


def _plan_call(price: float, atr: float, levels: dict) -> dict:
    res = _levels_above(levels, price, ("pivot", "r1", "r2", "day_high"))
    sup = _levels_below(levels, price, ("pivot", "s1", "s2"))

    setup = res[0] if res else _round(price + 0.5 * atr)
    entry = _round(max(price, setup))
    target1 = res[1] if len(res) > 1 else _round(entry + 1.5 * atr)
    target2 = res[2] if len(res) > 2 else _round(entry + 2.5 * atr)

    atr_stop = entry - 1.5 * atr
    tech_stop = sup[0] if sup else None
    # Stop más ceñido (el más alto) pero siempre por debajo de la entrada.
    stop = _round(max(tech_stop, atr_stop) if tech_stop is not None else atr_stop)

    rr = _round((target1 - entry) / (entry - stop), 2) if entry > stop else 0.0
    return {
        "setup_level": _round(setup),
        "entry": entry,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "rr": rr,
    }


def _plan_put(price: float, atr: float, levels: dict) -> dict:
    sup = _levels_below(levels, price, ("pivot", "s1", "s2", "day_low"))
    res = _levels_above(levels, price, ("pivot", "r1", "r2"))

    setup = sup[0] if sup else _round(price - 0.5 * atr)
    entry = _round(min(price, setup))
    target1 = sup[1] if len(sup) > 1 else _round(entry - 1.5 * atr)
    target2 = sup[2] if len(sup) > 2 else _round(entry - 2.5 * atr)

    atr_stop = entry + 1.5 * atr
    tech_stop = res[0] if res else None
    # Stop más ceñido (el más bajo) pero siempre por encima de la entrada.
    stop = _round(min(tech_stop, atr_stop) if tech_stop is not None else atr_stop)

    rr = _round((entry - target1) / (stop - entry), 2) if stop > entry else 0.0
    return {
        "setup_level": _round(setup),
        "entry": entry,
        "stop": stop,
        "target1": target1,
        "target2": target2,
        "rr": rr,
    }


def decision_signal(ticker: str, regime: dict | None = None) -> dict:
    """Señal estructurada. GRATIS, sin IA. `regime` opcional para reusar (Paso 6)."""
    ticker = ticker.upper().strip()
    a = analyze_ticker(ticker)  # puede lanzar ValueError (ticker inválido)
    price = a.price
    atr = a.atr if a.atr and a.atr > 0 else max(price * 0.01, 0.01)

    # --- Datos de apoyo (resistentes: si uno falla, seguimos sin él) ---
    levels: dict = {}
    try:
        levels = intraday_data(ticker).get("levels", {})
    except Exception:  # noqa: BLE001
        levels = {}

    if regime is None:
        try:
            regime = market_regime()
        except Exception:  # noqa: BLE001
            regime = None

    opening = None
    try:
        opening = opening_analysis(ticker)
    except Exception:  # noqa: BLE001
        opening = None

    # Ventana horaria de la sesión (edge por hora del día). Informativa siempre.
    session = _session_window()

    # --- Votación de factores ---
    votes: list[dict] = []

    def add(factor: str, weight: int, vote: int, detail: str):
        votes.append(
            {
                "factor": factor,
                "weight": weight,
                "vote": "CALL" if vote > 0 else "PUT" if vote < 0 else "—",
                "_v": vote,
                "detail": detail,
            }
        )

    tv = 1 if a.trend == "Alcista" else -1 if a.trend == "Bajista" else 0
    add("Tendencia diaria", 2, tv, a.trend)

    if opening is not None:
        vv = 1 if opening["above_vwap"] else -1
        add("Precio vs VWAP", 2, vv, f"{'sobre' if vv > 0 else 'bajo'} VWAP {opening['vwap']}")
        ob = opening["bias"]
        ov = 1 if ob == "CALL" else -1 if ob == "PUT" else 0
        add("Señal de apertura", 2, ov, opening["signal"])

    if regime is not None:
        rs = regime.get("score", 0)
        rv = 1 if rs >= 10 else -1 if rs <= -10 else 0
        add("Régimen de mercado", 2, rv, f"{regime.get('regime')} ({rs:+})")

    pivot = levels.get("pivot")
    if pivot:
        pv = 1 if price > pivot else -1 if price < pivot else 0
        add("Precio vs Pivot", 1, pv, f"pivot {pivot}")

    mv = 1 if a.macd_hist > 0 else -1 if a.macd_hist < 0 else 0
    add("MACD histograma", 1, mv, f"{a.macd_hist}")

    rv2 = 1 if a.rsi > 55 else -1 if a.rsi < 45 else 0
    add("RSI", 1, rv2, f"{a.rsi}")

    # --- Cálculo del veredicto ---
    neto = sum(v["weight"] * v["_v"] for v in votes)
    opin_weight = sum(v["weight"] for v in votes if v["_v"] != 0)
    n_opin = sum(1 for v in votes if v["_v"] != 0)
    agreement = abs(neto) / opin_weight if opin_weight else 0.0

    direction = "CALL" if neto > 0 else "PUT" if neto < 0 else "NEUTRAL"

    confidence = round(agreement * 100)
    if a.volume_ratio >= 1.2:
        confidence += 8  # volumen confirma
    elif a.volume_ratio < 0.7:
        confidence -= 8  # participación floja
    if n_opin < 4:
        confidence = min(confidence, 60)  # pocos factores => no sobre-confiar
    confidence = max(0, min(95, confidence))

    # --- Vetos y degradaciones ---
    veto = None
    if regime is not None and regime.get("regime") == "NO OPERAR":
        veto = regime.get("veto_reason") or "Régimen de mercado: NO OPERAR."

    plan = None
    if veto:
        signal = "NO OPERAR"
    elif direction == "NEUTRAL" or agreement < MIN_AGREEMENT:
        signal = "NO OPERAR"
        veto = "Factores contradictorios: sin ventaja clara."
    elif confidence < MIN_CONFIDENCE:
        signal = "NO OPERAR"
        veto = f"Confianza insuficiente ({confidence}%)."
    else:
        plan = _plan_call(price, atr, levels) if direction == "CALL" else _plan_put(price, atr, levels)
        prox = _proximity(price, plan["entry"], atr)
        plan.update(prox)
        if plan["rr"] < MIN_RR:
            signal = "NO OPERAR"
            veto = f"R:R desfavorable ({plan['rr']}): el riesgo no compensa."
            plan = None
        elif prox["entry_distance_atr"] > MAX_ENTRY_ATR:
            signal = "NO OPERAR"
            veto = (
                f"Entrada lejos del precio ({prox['entry_distance_atr']} ATR): "
                "estarías persiguiendo un movimiento ya extendido."
            )
            plan = None
        else:
            # Penaliza la confianza por TRES factores que degradan (ninguno veta
            # solo): distancia de entrada, hora del día (mediodía = chop) y
            # sobre-extensión del RSI (no entrar en agotamiento). Si la confianza
            # cae bajo el mínimo, entonces NO OPERAR citando la causa dominante.
            oe = _overextension(a.rsi, direction)
            plan.update(oe)
            adj = prox["proximity_factor"] * session["session_factor"] * oe["overext_factor"]
            confidence = max(0, min(95, round(confidence * adj)))
            if confidence < MIN_CONFIDENCE:
                signal = "NO OPERAR"
                # La causa es el factor con el peor (menor) multiplicador.
                causa = min(
                    (
                        (prox["proximity_factor"], prox["proximity_label"]),
                        (session["session_factor"], session["session_label"]),
                        (oe["overext_factor"], oe["overext_label"]),
                    ),
                    key=lambda t: t[0],
                )[1]
                veto = (
                    f"Confianza insuficiente tras ajustes ({confidence}%): {causa}."
                )
                plan = None
            else:
                signal = direction

    # --- Razón y riesgo (texto) ---
    target_v = 1 if signal == "CALL" else -1 if signal == "PUT" else 0
    if target_v:
        a_favor = [v["factor"] for v in votes if v["_v"] == target_v]
        en_contra = [v["factor"] for v in votes if v["_v"] == -target_v]
        reason = "A favor: " + ", ".join(a_favor)
        if en_contra:
            reason += " · En contra: " + ", ".join(en_contra)
    else:
        reason = veto or "No hay confluencia suficiente para operar."

    if plan:
        invalida = "pierde" if signal == "CALL" else "supera"
        risk = (
            f"Invalida la tesis si {invalida} {plan['stop']}. "
            f"R:R objetivo {plan['rr']}. No arriesgues más del 1-2% de la cuenta."
        )
        contract = (
            f"{signal} cerca del dinero (delta 0.40-0.60), vencimiento 1-4 semanas; "
            "evita far OTM y spreads anchos. Detalle en el módulo de contratos."
        )
    else:
        risk = "Sin operación: esperar a que aparezca ventaja."
        contract = None

    return {
        "ticker": ticker,
        "price": price,
        "signal": signal,
        "direction": direction,
        "confidence": confidence,
        "agreement": round(agreement, 2),
        "net_score": neto,
        "plan": plan,
        "contract_hint": contract,
        "reason": reason,
        "risk": risk,
        "veto_reason": veto if signal == "NO OPERAR" else None,
        "factors": [
            {k: v for k, v in vote.items() if k != "_v"} for vote in votes
        ],
        "session": session,
        "context": {
            "trend": a.trend,
            "classification": a.classification,
            "rsi": a.rsi,
            "atr": _round(atr),
            "volume_ratio": a.volume_ratio,
            "regime": regime.get("regime") if regime else None,
            "opening_signal": opening["signal"] if opening else None,
            "above_vwap": opening["above_vwap"] if opening else None,
        },
    }
