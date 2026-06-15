"""
Diario de decisiones: registro MANUAL de lo que el usuario decide (CALL/PUT/ESPERAR).

Es solo una bitacora para aprender despues que funciono y que no. NO ejecuta
ordenes ni recomienda comprar: el usuario decide, ejecuta en su broker y aqui
deja constancia con su tesis y el contexto del momento.

Persistido en data/journal.json (lista de entradas). Sin base de datos.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

JOURNAL_FILE = Path(__file__).resolve().parent.parent / "data" / "journal.json"
TZ = ZoneInfo("America/New_York")

VALID_DECISIONS = {"CALL", "PUT", "ESPERAR"}
VALID_OUTCOMES = {"en_curso", "acierto", "fallo", "neutra"}


def _normalize_contract(contract: dict | None, decision: str) -> dict | None:
    """Datos del contrato para el seguimiento de salida (Paso 5).

    Solo tiene sentido en posiciones CALL/PUT. Necesita strike, vencimiento y la
    prima de entrada (lo que pagaste): los objetivos +15/+20/+30% son sobre la
    PRIMA, no sobre la accion. `stop` (nivel del subyacente, del plan del Paso 3)
    es opcional y sirve para detectar la tesis invalidada. Si faltan datos clave
    o la decision es ESPERAR, devuelve None (posicion sin seguimiento de prima).
    """
    if not contract or decision not in ("CALL", "PUT"):
        return None
    try:
        kind = str(contract.get("type", "")).lower().strip()
        if kind not in ("call", "put"):
            kind = "call" if decision == "CALL" else "put"
        strike = float(contract.get("strike"))
        expiry = str(contract.get("expiry", "")).strip()
        entry_premium = float(contract.get("entry_premium"))
    except (TypeError, ValueError):
        return None
    if not expiry or strike <= 0 or entry_premium <= 0:
        return None

    out = {
        "type": kind,
        "strike": round(strike, 2),
        "expiry": expiry,
        "entry_premium": round(entry_premium, 2),
    }
    stop = contract.get("stop")
    if stop is not None:
        try:
            out["stop"] = round(float(stop), 2)
        except (TypeError, ValueError):
            pass
    return out


def _ensure_file() -> None:
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not JOURNAL_FILE.exists():
        JOURNAL_FILE.write_text("[]", encoding="utf-8")


def _load() -> list[dict]:
    _ensure_file()
    return json.loads(JOURNAL_FILE.read_text(encoding="utf-8"))


def _save(entries: list[dict]) -> None:
    JOURNAL_FILE.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_journal() -> list[dict]:
    """Todas las entradas, mas recientes primero."""
    return sorted(_load(), key=lambda e: e.get("ts", ""), reverse=True)


def add_entry(
    ticker: str,
    decision: str,
    price: float = 0.0,
    note: str = "",
    context: dict | None = None,
    contract: dict | None = None,
) -> dict:
    """Anade una decision al diario. `decision` debe ser CALL, PUT o ESPERAR.

    `contract` (opcional) adjunta el contrato de opciones para el seguimiento de
    salida del Paso 5: {type, strike, expiry, entry_premium, stop?}.
    """
    dec = (decision or "").upper().strip()
    if dec not in VALID_DECISIONS:
        raise ValueError(
            f"Decision invalida '{decision}'. Usa: {', '.join(sorted(VALID_DECISIONS))}."
        )

    entry = {
        "id": str(int(time.time() * 1000)),
        "ts": datetime.now(TZ).isoformat(timespec="seconds"),
        "ticker": (ticker or "").upper().strip(),
        "decision": dec,
        "price": round(float(price or 0.0), 2),
        "note": (note or "").strip(),
        "context": context or {},
        "contract": _normalize_contract(contract, dec),
        "outcome": "en_curso",
    }
    entries = _load()
    entries.append(entry)
    _save(entries)
    return entry


def set_outcome(entry_id: str, outcome: str) -> dict | None:
    """Marca el resultado de una decision. Devuelve la entrada o None si no existe."""
    out = (outcome or "").strip()
    if out not in VALID_OUTCOMES:
        raise ValueError(
            f"Resultado invalido '{outcome}'. Usa: {', '.join(sorted(VALID_OUTCOMES))}."
        )

    entries = _load()
    updated = None
    for e in entries:
        if e.get("id") == entry_id:
            e["outcome"] = out
            updated = e
            break
    if updated is not None:
        _save(entries)
    return updated


def delete_entry(entry_id: str) -> list[dict]:
    """Elimina una entrada por id. Devuelve la lista actualizada (recientes primero)."""
    entries = [e for e in _load() if e.get("id") != entry_id]
    _save(entries)
    return get_journal()
