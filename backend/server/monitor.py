"""
FASE 3 - Bucle de monitoreo.

Recorre la watchlist durante el horario de mercado. Calcula indicadores (gratis)
y SOLO cuando la "firma de senales" cambia respecto a la ultima revision, llama
al LLM y envia una alerta a Telegram. Asi evitamos spam y ahorramos API de OpenAI.

El estado se persiste en data/monitor_state.json para no re-alertar al reiniciar.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from core.intraday import intraday_data
from core.market_regime import market_regime
from core.signal import decision_signal
from core.telegram_bot import format_level_alert, format_signal_alert, send_message
from server.signals_log import record_signal
from server.watchlist import get_watchlist

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "monitor_state.json"
MARKET_TZ = ZoneInfo("America/New_York")

# Guarda anti-flapping: no re-alertar el mismo ticker dentro de este lapso aunque
# la firma oscile alrededor de un umbral. Configurable via .env.
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "900"))

# Cooldown independiente por NIVEL: si el precio oscila sobre la misma linea no
# queremos un aviso cada pasada. Configurable via .env (por defecto 30 min).
LEVEL_ALERT_COOLDOWN = int(os.getenv("LEVEL_ALERT_COOLDOWN", "1800"))

# Escalera de niveles a vigilar (nombre visible -> clave en data["levels"]).
LADDER_KEYS = [
    ("R2", "r2"),
    ("R1", "r1"),
    ("Pivot", "pivot"),
    ("S1", "s1"),
    ("S2", "s2"),
]


# --------------------------------------------------------------------------- #
#  Horario de mercado (NYSE: Lun-Vie 9:30-16:00 ET). No maneja feriados.
# --------------------------------------------------------------------------- #
def is_market_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(MARKET_TZ)
    if now.weekday() >= 5:  # 5=sabado, 6=domingo
        return False
    open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_t <= now <= close_t


# --------------------------------------------------------------------------- #
#  Estado persistente
# --------------------------------------------------------------------------- #
def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _now_str() -> str:
    return datetime.now(MARKET_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


# --------------------------------------------------------------------------- #
#  Disparadores de NIVEL intradia (gratis, sin IA)
# --------------------------------------------------------------------------- #
def _check_levels(ticker: str, entry: dict, force: bool = False) -> None:
    """Detecta cruces de niveles intradia y avisa por Telegram.

    Compara el precio actual contra el de la pasada anterior (`entry["intra_price"]`).
    Si entre ambos quedo un nivel de la escalera, hubo un cruce:
      - hacia ARRIBA  (prev < nivel <= actual) -> sesgo CALL
      - hacia ABAJO   (prev > nivel >= actual) -> sesgo PUT
    Muta `entry` con el ultimo precio y el timestamp por nivel (cooldown propio).
    """
    try:
        data = intraday_data(ticker)
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  {ticker}: no se pudo leer intradia para niveles ({exc}).")
        return

    current = data.get("current_price")
    levels = data.get("levels", {})
    if not current:
        return

    prev = entry.get("intra_price")
    level_alerts: dict = entry.get("level_alerts", {})

    # Primera lectura del ticker: solo fijamos referencia, sin alertar.
    if prev is None:
        entry["intra_price"] = current
        return

    now = time.time()
    for name, key in LADDER_KEYS:
        lv = levels.get(key)
        if not lv:
            continue
        crossed_up = prev < lv <= current
        crossed_down = prev > lv >= current
        if not (crossed_up or crossed_down):
            continue

        last = level_alerts.get(key)
        if last and not force and (now - last) < LEVEL_ALERT_COOLDOWN:
            print(f"  ⏳ {ticker}: cruce de {name} en cooldown, lo salto.")
            continue

        direction = "up" if crossed_up else "down"
        try:
            send_message(
                format_level_alert(
                    ticker, name, round(lv, 2), round(current, 2), direction
                )
            )
            level_alerts[key] = now
            flecha = "🚀" if crossed_up else "🔻"
            print(f"  {flecha} {ticker}: cruce de {name} ({direction}) alertado.")
        except Exception as exc:  # noqa: BLE001
            print(f"     ❌ No se pudo alertar cruce de {name}: {exc}")

    entry["level_alerts"] = level_alerts
    entry["intra_price"] = current


# --------------------------------------------------------------------------- #
#  Una pasada de revision sobre toda la watchlist
# --------------------------------------------------------------------------- #
def check_once(force: bool = False) -> None:
    """Revisa cada ticker. Alerta la señal CALL/PUT directa solo si cambió.

    Usa core.signal.decision_signal (determinista, GRATIS, sin IA). El veredicto
    es la propia señal (CALL / PUT / NO OPERAR); alertamos cuando esa señal cambia
    respecto a la última pasada, respetando el cooldown anti-flapping.
    """
    state = _load_state()
    tickers = get_watchlist()
    print(f"[{_now_str()}] Revisando {len(tickers)} ticker(s): {', '.join(tickers)}")

    # Régimen de mercado: se calcula UNA vez por pasada y se reutiliza (eficiencia).
    try:
        regime = market_regime()
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠️  No se pudo leer el régimen de mercado ({exc}). Sigo sin él.")
        regime = None

    for ticker in tickers:
        try:
            sig = decision_signal(ticker, regime=regime)
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠️  {ticker}: error al analizar ({exc}). Lo salto.")
            continue

        new_sig = sig["signal"]  # "CALL" / "PUT" / "NO OPERAR"
        entry = state.get(ticker, {})
        prev_sig = entry.get("signature")
        last_alert = entry.get("last_alert")

        changed = new_sig != prev_sig

        # Anti-flapping: si cambio pero alertamos hace poco, esperamos.
        elapsed_ok = True
        if last_alert and not force:
            elapsed = time.time() - last_alert
            elapsed_ok = elapsed >= ALERT_COOLDOWN_SECONDS

        if force or (changed and elapsed_ok):
            reason = "forzado" if force else f"señal: {prev_sig or '—'} → {new_sig}"
            print(f"  🔔 {ticker}: ALERTA ({reason}).")
            try:
                send_message(format_signal_alert(sig))
                entry["signature"] = new_sig
                entry["last_alert"] = time.time()
                print(f"     ✅ Alerta enviada ({new_sig}, conf {sig['confidence']}%).")
                # Anota la señal buena (CALL/PUT con plan) para medir aciertos
                # luego. Las NO OPERAR no se registran (record_signal las ignora).
                rec = record_signal(sig)
                if rec:
                    print(f"     📝 Registrada para seguimiento (id {rec['id']}).")
            except Exception as exc:  # noqa: BLE001
                print(f"     ❌ No se pudo alertar: {exc}")
        elif changed and not elapsed_ok:
            print(f"  ⏳ {ticker}: cambio detectado pero en cooldown. Esperando.")
        else:
            entry["signature"] = new_sig
            print(f"  ➖ {ticker}: sin cambios ({new_sig}).")

        # Disparadores de nivel intradia (gratis, independientes de la firma/IA).
        _check_levels(ticker, entry, force=force)

        # Persistimos SIEMPRE el entry (precio de referencia, cooldowns por nivel).
        state[ticker] = entry

    _save_state(state)


# --------------------------------------------------------------------------- #
#  Bucle principal
# --------------------------------------------------------------------------- #
def run_loop(interval_seconds: int = 300) -> None:
    print(
        f"🟢 Monitor iniciado. Intervalo: {interval_seconds}s | "
        f"Cooldown: {ALERT_COOLDOWN_SECONDS}s\n"
    )
    while True:
        if is_market_open():
            check_once()
        else:
            print(f"[{_now_str()}] Mercado cerrado. En espera.")
        time.sleep(interval_seconds)
