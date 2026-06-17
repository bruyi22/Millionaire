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

import yfinance as yf

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
        "source": "signal",        # motor diario CALL/PUT (verificación por días)
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


def record_playbook_signal(pb: dict) -> dict | None:
    """Anota una señal de COMPRA del playbook INTRADÍA. Devuelve el registro o None.

    Solo registra veredictos de compra (reclaim/ruptura) con plan. A diferencia del
    motor diario, estas se verifican DENTRO de la misma sesión (paso B intradía),
    por eso llevan `source="playbook"`. Si el setup no tenía un nivel claro arriba
    (target None), usamos un objetivo proxy de +0.5% para poder medir el acierto.
    """
    verdict = pb.get("verdict") or {}
    action = verdict.get("action", "")
    plan = verdict.get("plan")
    if not action.startswith("COMPRAR") or not plan:
        return None

    entry = plan.get("entry")
    stop = plan.get("stop")
    target = plan.get("target")
    target_kind = "nivel"
    if not target and entry:
        target = round(entry * 1.005, 2)   # +0.5% como objetivo medible
        target_kind = "proxy"

    now = datetime.now(MARKET_TZ)
    record = {
        "id": f"{pb['ticker']}-{now.strftime('%Y%m%d%H%M%S')}",
        "ts_et": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "ts_intraday": now.strftime("%Y-%m-%d %H:%M"),  # para alinear con velas 5m
        "date": now.strftime("%Y-%m-%d"),
        "ticker": pb["ticker"],
        "source": "playbook",
        "setup": action,            # COMPRAR (reclaim) | COMPRAR (ruptura)
        "direction": "CALL",        # el playbook solo da entradas alcistas (long)
        "price_at_signal": pb.get("current_price"),
        "entry": entry,
        "stop": stop,
        "target1": target,
        "target_kind": target_kind,
        "horizon": "intradia",      # se resuelve en la misma sesión
        # Campos que rellena la VERIFICACIÓN intradía (paso B):
        "status": "abierta",        # abierta | acierto | fallo | ambigua | expirada
        "resolved_date": None,
        "resolved_price": None,
        "move_pct": None,
    }

    log = _load()
    log.append(record)
    _save(log)
    return record


def _daily_bars_since(ticker: str, start_date: str) -> list[dict]:
    """Velas diarias (date/high/low/close) desde `start_date` (inclusive) a hoy.

    Solo lectura. Devuelve [] si no hay datos (ticker raro o sin sesiones aún).
    """
    df = yf.Ticker(ticker).history(period="3mo", interval="1d")
    df = df[df["High"].notna() & df["Low"].notna()]
    if df.empty:
        return []
    bars: list[dict] = []
    for idx, row in df.iterrows():
        d = idx.strftime("%Y-%m-%d")
        if d < start_date:  # comparación de fechas ISO como texto: válida
            continue
        bars.append(
            {"date": d, "high": float(row["High"]), "low": float(row["Low"]), "close": float(row["Close"])}
        )
    return bars


def _evaluate(record: dict) -> dict | None:
    """Decide el resultado de UNA señal abierta mirando target1 vs stop.

    Regla (realista de trade): dentro del horizonte de N días hábiles, ¿el precio
    alcanzó el TARGET1 antes que el STOP? Recorre día a día:
      - CALL: high>=target1 => acierto · low<=stop => fallo
      - PUT:  low<=target1  => acierto · high>=stop => fallo
      - Si ambos ocurren el MISMO día => 'ambigua' (no sabemos el orden intradía).
      - Si pasan los N días sin tocar ninguno => 'expirada'.
    Devuelve el `record` mutado si se resolvió, o None si sigue abierta (aún
    dentro del horizonte y sin datos suficientes para cerrar).
    """
    # Las del playbook son INTRADÍA: las verifica _evaluate_intraday (paso B).
    if record.get("source") == "playbook":
        return _evaluate_intraday(record)

    direction = record["direction"]
    target, stop = record["target1"], record["stop"]
    price0 = record["price_at_signal"]
    horizon = record.get("horizon_days", HORIZON_DAYS)

    bars = _daily_bars_since(record["ticker"], record["date"])
    if not bars:
        return None
    window = bars[:horizon]  # solo los primeros N días hábiles desde la señal

    def close(status: str, price: float, date: str) -> dict:
        record["status"] = status
        record["resolved_date"] = date
        record["resolved_price"] = round(price, 2)
        record["move_pct"] = round((price / price0 - 1) * 100, 2) if price0 else None
        return record

    for bar in window:
        if direction == "CALL":
            hit, miss = bar["high"] >= target, bar["low"] <= stop
        else:  # PUT
            hit, miss = bar["low"] <= target, bar["high"] >= stop
        if hit and miss:
            return close("ambigua", bar["close"], bar["date"])
        if hit:
            return close("acierto", target, bar["date"])
        if miss:
            return close("fallo", stop, bar["date"])

    # No tocó target ni stop. Solo cerramos como 'expirada' si el horizonte YA
    # transcurrió por completo (hay >= horizon velas); si no, sigue abierta.
    if len(window) >= horizon:
        last = window[-1]
        return close("expirada", last["close"], last["date"])
    return None


def _intraday_bars_after(ticker: str, date_str: str, after_ts: str) -> list[dict]:
    """Velas 5m del día `date_str` con hora >= `after_ts` ('YYYY-MM-DD HH:MM').

    yfinance indexa las velas intradía en la zona del mercado (ET), igual que el
    timestamp con que guardamos la señal, así que la comparación de texto vale.
    """
    df = yf.Ticker(ticker).history(period="5d", interval="5m")
    df = df[df["High"].notna() & df["Low"].notna()]
    if df.empty:
        return []
    bars: list[dict] = []
    for idx, row in df.iterrows():
        ts = idx.strftime("%Y-%m-%d %H:%M")
        if ts[:10] != date_str or ts < after_ts:
            continue
        bars.append({"ts": ts, "high": float(row["High"]),
                     "low": float(row["Low"]), "close": float(row["Close"])})
    return bars


def _evaluate_intraday(record: dict) -> dict | None:
    """Verifica UNA señal del playbook (long) DENTRO de su sesión, vela a vela 5m.

    Desde la vela de la señal en adelante (mismo día):
      - high >= target1 => acierto · low <= stop => fallo
      - si ambos en la MISMA vela => 'ambigua' (no sabemos el orden dentro de 5m)
      - si la sesión terminó sin tocar ninguno => 'expirada'
    Devuelve el record mutado si se resolvió, o None si la sesión sigue en curso.
    """
    target, stop = record["target1"], record["stop"]
    price0 = record["price_at_signal"]
    after = record.get("ts_intraday") or (record["date"] + " 00:00")

    bars = _intraday_bars_after(record["ticker"], record["date"], after)
    if not bars:
        return None

    def close(status: str, price: float, ts: str) -> dict:
        record["status"] = status
        record["resolved_date"] = ts
        record["resolved_price"] = round(price, 2)
        record["move_pct"] = round((price / price0 - 1) * 100, 2) if price0 else None
        return record

    for bar in bars:
        hit, miss = bar["high"] >= target, bar["low"] <= stop  # long
        if hit and miss:
            return close("ambigua", bar["close"], bar["ts"])
        if hit:
            return close("acierto", target, bar["ts"])
        if miss:
            return close("fallo", stop, bar["ts"])

    # Recorrió las velas disponibles sin tocar nada. Solo cerramos 'expirada' si la
    # sesión YA terminó (día pasado, o ya pasaron las 16:00 ET de hoy).
    now = datetime.now(MARKET_TZ)
    session_over = record["date"] < now.strftime("%Y-%m-%d") or now.hour >= 16
    if session_over:
        last = bars[-1]
        return close("expirada", last["close"], last["ts"])
    return None


def review_open_signals() -> dict:
    """Verifica TODAS las señales abiertas y persiste los resultados.

    Pensado para correr 1 vez al día (cron aparte tras el cierre). Devuelve un
    resumen de qué se resolvió en esta pasada.
    """
    log = _load()
    resolved = {"acierto": 0, "fallo": 0, "expirada": 0, "ambigua": 0}
    changed = False

    for record in log:
        if record["status"] != "abierta":
            continue
        try:
            res = _evaluate(record)
        except Exception:  # noqa: BLE001  (un ticker no debe tumbar el resto)
            res = None
        if res is not None:
            resolved[res["status"]] = resolved.get(res["status"], 0) + 1
            changed = True

    if changed:
        _save(log)
    return {"revisadas": sum(resolved.values()), "detalle": resolved, "stats": stats()}


def get_log() -> list[dict]:
    """Devuelve el registro completo (para la API/UI o inspección)."""
    return _load()


def _stats_for(records: list[dict]) -> dict:
    """Aciertos/fallos/win-rate de un subconjunto del registro."""
    cerradas = [r for r in records if r["status"] in ("acierto", "fallo")]
    aciertos = sum(1 for r in cerradas if r["status"] == "acierto")
    n = len(cerradas)
    return {
        "total": len(records),
        "abiertas": sum(1 for r in records if r["status"] == "abierta"),
        "cerradas": n,
        "aciertos": aciertos,
        "fallos": n - aciertos,
        "win_rate": round(aciertos / n * 100, 1) if n else None,
    }


def stats() -> dict:
    """Resumen del track record, global y SEPARADO por fuente.

    `by_source` distingue el motor diario ('signal') del playbook intradía
    ('playbook'), que es justo lo que queremos comparar para saber cuál acierta
    más. Los registros viejos sin 'source' cuentan como 'signal'.
    """
    log = _load()
    overall = _stats_for(log)
    overall["by_source"] = {
        "signal": _stats_for([r for r in log if r.get("source", "signal") == "signal"]),
        "playbook": _stats_for([r for r in log if r.get("source") == "playbook"]),
    }
    return overall
