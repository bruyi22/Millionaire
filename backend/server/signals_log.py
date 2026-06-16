"""
FASE 8 - Registro de señales para medir aciertos (track record).

Cada vez que el monitor manda una alerta BUENA (CALL/PUT con plan), la anotamos
aquí con el precio del momento y los niveles (entry/stop/target). Más tarde, el
paso de VERIFICACIÓN comprueba si el precio llegó al target1 ANTES que al stop
dentro de un horizonte, y marca acierto/fallo. Con el tiempo eso da un % de
acierto real por confianza/ticker para ir afinando el motor.

Sin base de datos: un simple JSON (data/signals_log.json) versionado en el repo,
igual que monitor_state.json. El cron lo commitea de vuelta entre ejecuciones.

NO ejecuta órdenes: solo registra y mide.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "signals_log.json"
MARKET_TZ = ZoneInfo("America/New_York")

# Horizonte por defecto: días HÁBILES que damos a una señal para cumplirse.
# Compras opciones de 1-4 semanas, así que 5 días (≈1 semana) es un primer punto
# razonable. Si una señal no toca target ni stop en ese plazo => "expirada".
HORIZON_DAYS = 5


def _load() -> list[dict]:
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def _save(log: list[dict]) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


def record_signal(sig: dict) -> dict | None:
    """Anota una señal CALL/PUT con plan. Devuelve el registro creado, o None.

    Solo registra señales operables (tienen dirección y plan con target/stop).
    Las NO OPERAR no se anotan: no hay nada que verificar.
    """
    signal = sig.get("signal")
    plan = sig.get("plan")
    if signal not in ("CALL", "PUT") or not plan:
        return None

    now = datetime.now(MARKET_TZ)
    record = {
        "id": f"{sig['ticker']}-{now.strftime('%Y%m%d%H%M%S')}",
        "ts_et": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "date": now.strftime("%Y-%m-%d"),
        "ticker": sig["ticker"],
        "direction": signal,
        "price_at_signal": sig.get("price"),
        "confidence": sig.get("confidence"),
        "entry": plan.get("entry"),
        "stop": plan.get("stop"),
        "target1": plan.get("target1"),
        "rr": plan.get("rr"),
        "horizon_days": HORIZON_DAYS,
        # Campos que rellena la VERIFICACIÓN (paso B):
        "status": "abierta",       # abierta | acierto | fallo | expirada
        "resolved_date": None,
        "resolved_price": None,
        "move_pct": None,
    }

    log = _load()
    log.append(record)
    _save(log)
    return record


def get_log() -> list[dict]:
    """Devuelve el registro completo (para la API/UI o inspección)."""
    return _load()


def stats() -> dict:
    """Resumen rápido del track record: aciertos/fallos y win-rate."""
    log = _load()
    cerradas = [r for r in log if r["status"] in ("acierto", "fallo")]
    aciertos = sum(1 for r in cerradas if r["status"] == "acierto")
    n = len(cerradas)
    return {
        "total": len(log),
        "abiertas": sum(1 for r in log if r["status"] == "abierta"),
        "cerradas": n,
        "aciertos": aciertos,
        "fallos": n - aciertos,
        "win_rate": round(aciertos / n * 100, 1) if n else None,
    }
