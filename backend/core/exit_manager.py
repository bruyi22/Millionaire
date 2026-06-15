"""
FASE 5 (roadmap) - Modulo de SALIDA.

Una vez DENTRO de una posicion (registrada en el diario con su contrato), este
modulo dice cuando recoger ganancias o defenderse. Lee las posiciones abiertas
del diario (decision CALL/PUT, outcome 'en_curso', con datos de contrato), busca
la PRIMA ACTUAL del contrato exacto en la cadena y la compara con la prima de
entrada para emitir UNA senal de salida.

Filosofia: los objetivos +15/+20/+30% son sobre la PRIMA (lo que pagaste), no
sobre la accion. Igual que el resto: GRATIS (sin IA) y NUNCA ejecuta ordenes;
solo avisa para que TU decidas y ejecutes en tu broker.
"""

from __future__ import annotations

from datetime import date, datetime

import yfinance as yf

from core.options import _row_to_contract, _safe, _underlying_price
from server import journal

# Escalera de toma de ganancias (sobre la prima). Cada nivel: (pct, accion).
PROFIT_LADDER = [
    (30, "Recoge fuerte o deja correr con trailing ajustado: +30% es excelente."),
    (20, "Asegura: recoge mas o sube el stop mental a +10% para no devolver."),
    (15, "Recoge parcial (~1/3): bloquea ganancia, deja correr el resto."),
]

DEFENSIVE_PCT = -25.0   # la prima cae 25% desde la entrada -> salida defensiva
THETA_DTE_WARN = 5      # pocos dias al vencimiento sin moverse -> el tiempo corre


def _current_contract(ticker: str, expiry: str, kind: str, strike: float):
    """Lee la foto actual del contrato exacto (strike/venc/tipo) de la cadena.

    Devuelve (contract_dict, underlying_price, dte). Reusa los helpers de
    core.options para no duplicar el calculo de mid/Greeks/break-even.
    """
    tk = yf.Ticker(ticker)
    expiries = list(tk.options)
    if not expiries:
        raise ValueError(f"'{ticker}' no tiene opciones listadas.")
    if expiry not in expiries:
        raise ValueError(f"Vencimiento '{expiry}' ya no esta disponible para {ticker}.")

    underlying = _underlying_price(tk)
    chain = tk.option_chain(expiry)
    df = chain.calls if kind == "call" else chain.puts
    if df.empty:
        raise ValueError(f"Sin {kind}s para {ticker} {expiry}.")

    # Fila del strike exacto (o el mas cercano si el strike ya no existe).
    idx = (df["strike"] - strike).abs().idxmin()
    row = df.loc[idx]

    try:
        dte = (datetime.strptime(expiry, "%Y-%m-%d").date() - date.today()).days
    except ValueError:
        dte = None

    contract = _row_to_contract(row, kind, underlying, dte)
    return contract, underlying, dte


def _thesis_broken(direction: str, underlying: float, stop: float | None) -> bool:
    """¿El subyacente cruzo el stop del plan? (tesis invalidada)."""
    if not stop or not underlying:
        return False
    if direction == "CALL":
        return underlying <= stop
    if direction == "PUT":
        return underlying >= stop
    return False


def _exit_signal(pnl_pct: float, thesis_broken: bool, dte: int | None) -> dict:
    """Decide UNA senal de salida por prioridad. Defensa primero, luego ganancia."""
    # 1) Tesis rota: el subyacente perdio el nivel clave. Maxima prioridad.
    if thesis_broken:
        return {
            "signal": "SALIR",
            "label": "🚪 Salir — tesis invalidada",
            "tone": "rojo",
            "action": "El subyacente cruzo el stop del plan: el motivo de entrada ya no existe. Sal aunque duela.",
        }
    # 2) Salida defensiva: la prima se desploma.
    if pnl_pct <= DEFENSIVE_PCT:
        return {
            "signal": "DEFENSIVA",
            "label": "🛑 Salida defensiva",
            "tone": "rojo",
            "action": f"La prima cae {round(pnl_pct)}% (umbral {round(DEFENSIVE_PCT)}%). Corta la perdida, no promedies.",
        }
    # 3) Toma de ganancias por escalera (de mayor a menor).
    for pct, action in PROFIT_LADDER:
        if pnl_pct >= pct:
            label = {30: "💰 Recoge fuerte (+30%)", 20: "✅ Asegura (+20%)", 15: "🟢 Parcial (+15%)"}[pct]
            return {"signal": f"GANANCIA_{pct}", "label": label, "tone": "verde", "action": action}
    # 4) El tiempo corre (theta) sin haber llegado a objetivos.
    if dte is not None and 0 <= dte <= THETA_DTE_WARN:
        return {
            "signal": "VIGILA_TIEMPO",
            "label": "⏳ Vigila el tiempo",
            "tone": "amarillo",
            "action": f"Quedan {dte}d al vencimiento y la prima no despega: theta acelera. Decide pronto.",
        }
    # 5) Nada que hacer: mantener.
    return {
        "signal": "MANTENER",
        "label": "⏸️ Mantener",
        "tone": "neutro",
        "action": "Dentro del plan, sin disparador. Deja correr y vigila los niveles.",
    }


def position_status(entry: dict) -> dict:
    """Estado de salida de UNA posicion abierta del diario (con contrato)."""
    contract = entry.get("contract") or {}
    ticker = entry.get("ticker", "")
    direction = entry.get("decision", "")
    kind = contract.get("type", "call" if direction == "CALL" else "put")
    strike = _safe(contract.get("strike"))
    expiry = contract.get("expiry", "")
    entry_premium = _safe(contract.get("entry_premium"))
    stop = contract.get("stop")

    base = {
        "id": entry.get("id"),
        "ticker": ticker,
        "decision": direction,
        "type": kind,
        "strike": strike,
        "expiry": expiry,
        "entry_premium": entry_premium,
        "stop": stop,
        "note": entry.get("note", ""),
        "ts": entry.get("ts"),
    }

    if not (ticker and expiry and strike > 0 and entry_premium > 0):
        return {**base, "error": "Posicion sin datos de contrato suficientes.", "signal": None}

    try:
        cur, underlying, dte = _current_contract(ticker, expiry, kind, strike)
    except Exception as exc:  # noqa: BLE001
        return {**base, "error": str(exc), "signal": None}

    current_premium = cur["mid"] or cur["last"]
    pnl_pct = (
        round((current_premium - entry_premium) / entry_premium * 100, 1)
        if entry_premium
        else 0.0
    )
    broken = _thesis_broken(direction, underlying, stop)
    verdict = _exit_signal(pnl_pct, broken, dte)

    return {
        **base,
        "underlying_price": round(underlying, 2),
        "current_premium": current_premium,
        "pnl_pct": pnl_pct,
        "dte": dte,
        "iv": cur["iv"],
        "theta": cur["theta"],
        "spread_pct": cur["spread_pct"],
        "thesis_broken": broken,
        "signal": verdict["signal"],
        "signal_label": verdict["label"],
        "tone": verdict["tone"],
        "action": verdict["action"],
        "error": None,
    }


def open_positions_status() -> list[dict]:
    """Todas las posiciones abiertas con seguimiento (CALL/PUT, en_curso, con contrato).

    Resistente: una posicion que falle (vencimiento expirado, ticker raro) no
    tumba al resto. Mas recientes primero.
    """
    out: list[dict] = []
    for e in journal.get_journal():
        if e.get("decision") not in ("CALL", "PUT"):
            continue
        if e.get("outcome") != "en_curso":
            continue
        if not e.get("contract"):
            continue
        try:
            out.append(position_status(e))
        except Exception as exc:  # noqa: BLE001
            out.append(
                {
                    "id": e.get("id"),
                    "ticker": e.get("ticker"),
                    "decision": e.get("decision"),
                    "error": str(exc),
                    "signal": None,
                }
            )
    return out
