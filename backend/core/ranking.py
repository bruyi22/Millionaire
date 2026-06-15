"""
FASE 6 (roadmap) - Ranking de oportunidades.

En vez de mirar ticker por ticker, ordena la watchlist por DONDE HAY VENTAJA HOY:
mejor / segundas / esperar. 100% DETERMINISTA y GRATIS (sin IA). Reutiliza la
señal del Paso 3 y el régimen del Paso 1 (calculado UNA vez y reusado para todos,
via el parametro `regime=` de decision_signal). Para las accionables (CALL/PUT)
adjunta tambien el contrato recomendado del Paso 4.

NO ejecuta ordenes: solo prioriza el foco de atencion.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.contracts import recommend_contracts
from core.market_regime import market_regime
from core.signal import decision_signal
from server import watchlist

# Peso del R:R en el score (la confianza es 0-95; el R:R suma hasta +15).
RR_BONUS = 5
RR_CAP = 3
NO_TRADE_FACTOR = 0.3  # las NO OPERAR se degradan para que caigan al fondo


def _opportunity_score(sig: dict) -> float:
    """Puntua la calidad de la oportunidad. Accionables arriba; NO OPERAR al fondo."""
    conf = sig.get("confidence", 0) or 0
    if sig.get("signal") not in ("CALL", "PUT"):
        return round(conf * NO_TRADE_FACTOR, 1)
    rr = (sig.get("plan") or {}).get("rr", 0) or 0
    return round(conf + min(rr, RR_CAP) * RR_BONUS, 1)


def _contract_hint(ticker: str, direction: str) -> dict | None:
    """Contrato recomendado para la direccion (Paso 4). Pasa direction para NO
    recomputar la señal. Resistente: si falla, devuelve None."""
    try:
        rec = recommend_contracts(ticker, direction=direction)
    except Exception:  # noqa: BLE001
        return None
    r = rec.get("recommended")
    if not r:
        return None
    return {
        "type": r["type"],
        "strike": r["strike"],
        "delta": r["delta"],
        "mid": r["mid"],
        "score": r["score"],
        "earnings_warning": rec.get("earnings_warning", False),
    }


def opportunity_ranking() -> dict:
    """Ordena la watchlist por ventaja hoy. GRATIS, sin IA, no ejecuta."""
    regime = None
    try:
        regime = market_regime()
    except Exception:  # noqa: BLE001
        regime = None

    rows: list[dict] = []
    for t in watchlist.get_watchlist():
        try:
            sig = decision_signal(t, regime=regime)
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "ticker": t.upper().strip(),
                    "signal": None,
                    "error": str(exc),
                    "score": -1.0,
                }
            )
            continue

        plan = sig.get("plan")
        row = {
            "ticker": sig["ticker"],
            "price": sig["price"],
            "signal": sig["signal"],
            "direction": sig["direction"],
            "confidence": sig["confidence"],
            "agreement": sig["agreement"],
            "reason": sig["reason"],
            "veto_reason": sig.get("veto_reason"),
            "plan": {
                "entry": plan["entry"],
                "stop": plan["stop"],
                "target1": plan["target1"],
                "target2": plan["target2"],
                "rr": plan["rr"],
            }
            if plan
            else None,
            "contract": _contract_hint(t, sig["direction"])
            if sig["signal"] in ("CALL", "PUT")
            else None,
            "error": None,
        }
        row["score"] = _opportunity_score(sig)
        rows.append(row)

    # Accionables (CALL/PUT) primero; dentro de cada grupo, mayor score arriba.
    rows.sort(
        key=lambda r: (1 if r.get("signal") in ("CALL", "PUT") else 0, r.get("score", 0)),
        reverse=True,
    )

    # Categoria por posicion: el primer accionable es la "Mejor".
    actionable_seen = 0
    for r in rows:
        if r.get("error"):
            r["category"] = "Error"
        elif r.get("signal") in ("CALL", "PUT"):
            actionable_seen += 1
            r["category"] = "Mejor" if actionable_seen == 1 else "Segunda"
        else:
            r["category"] = "Esperar"

    actionable = [r for r in rows if r.get("signal") in ("CALL", "PUT")]
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "regime": {
            "regime": regime.get("regime") if regime else None,
            "score": regime.get("score") if regime else None,
            "veto_reason": regime.get("veto_reason") if regime else None,
        },
        "best": actionable[0] if actionable else None,
        "count_actionable": len(actionable),
        "count_total": len(rows),
        "ranked": rows,
    }
