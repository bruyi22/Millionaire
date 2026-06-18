"""
FASE 3 - API FastAPI.

Sirve datos al frontend (Fase 4) y permite gestionar la watchlist.
NO ejecuta ordenes: es una API de solo lectura/analisis + edicion de watchlist.

Arrancar (desde la carpeta backend, con el venv activo):
    uvicorn server.main:app --reload --port 8000

Docs interactivas: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import os
import secrets
from dataclasses import asdict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from core.analysis import analyze_ticker, price_history  # noqa: E402
from core.contracts import recommend_contracts  # noqa: E402
from core.exit_manager import open_positions_status  # noqa: E402
from core.intraday import intraday_data  # noqa: E402
from core.journal_stats import journal_stats  # noqa: E402
from core.market_regime import market_regime  # noqa: E402
from core.opening import opening_analysis  # noqa: E402
from core.options import option_chain_analysis  # noqa: E402
from core.playbook import intraday_playbook  # noqa: E402
from core.ranking import opportunity_ranking  # noqa: E402
from core.signal import decision_signal  # noqa: E402
from server import journal, signals_log, watchlist  # noqa: E402
from server.monitor import check_once, is_market_open  # noqa: E402

app = FastAPI(title="Millionaire API", version="0.3.0")

# CORS abierto: uso personal/local. El frontend (Vite) corre en otro puerto.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "Millionaire API", "note": "solo analisis, no ejecuta ordenes"}


@app.get("/analyze/{ticker}")
def analyze(ticker: str):
    """Analiza un ticker (determinista, GRATIS, sin IA). Solo lectura."""
    try:
        result = analyze_ticker(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return asdict(result)


@app.get("/history/{ticker}")
def history(ticker: str, period: str = "6mo"):
    """Serie de precios + medias moviles para el grafico. Solo lectura."""
    try:
        return price_history(ticker, period=period)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/intraday/{ticker}")
def intraday(ticker: str, interval: str = "5m"):
    """Velas intradia + niveles tecnicos para el grafico en vivo. Solo lectura."""
    try:
        return intraday_data(ticker, interval=interval)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc




@app.get("/options/{ticker}")
def options(ticker: str, expiry: str | None = None, strikes: int = 6):
    """Cadena de opciones cerca del dinero + banderas de riesgo. Solo lectura."""
    try:
        return option_chain_analysis(ticker, expiry=expiry, n_strikes=strikes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/contracts/{ticker}")
def contracts(ticker: str, direction: str | None = None, expiry: str | None = None):
    """Contrato recomendado/agresivo/evitar para la dirección de la señal. GRATIS."""
    try:
        return recommend_contracts(ticker, direction=direction, expiry=expiry)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/market-regime")
def regime():
    """Market Regime Score: ¿el mercado permite operar hoy? GRATIS (sin IA)."""
    return market_regime()


@app.get("/ranking")
def ranking():
    """Ranking de la watchlist por ventaja hoy (mejor/segundas/esperar). GRATIS, sin
    IA. Reusa régimen + señal + contrato. Puede tardar unos segundos."""
    return opportunity_ranking()


@app.get("/opening/{ticker}")
def opening(ticker: str):
    """Análisis de la apertura 9:30-10:00 ET (rango, VWAP, patrones). GRATIS."""
    try:
        return opening_analysis(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/signal/{ticker}")
def signal(ticker: str):
    """Señal estructurada CALL/PUT/NO OPERAR (motor de confluencias). GRATIS."""
    try:
        return decision_signal(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/playbook/{ticker}")
def playbook(ticker: str):
    """Playbook INTRADÍA de momentum (5 min): VWAP, EMAs, MACD/RSI intradía,
    volumen y ruptura/reclaim. Veredicto para mirar EN VIVO desde el panel.
    GRATIS, sin IA. Solo lectura — no ejecuta órdenes."""
    try:
        return intraday_playbook(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# --------------------------------------------------------------------------- #
#  Tick del monitor (lo dispara un cron EXTERNO fiable, p.ej. cron-job.org)
#  GitHub Actions descarta los schedules de alta frecuencia, así que el reloj
#  intradía vive fuera y golpea aquí cada pocos minutos. NO ejecuta órdenes:
#  solo corre una pasada del monitor (que puede mandar alertas a Telegram).
# --------------------------------------------------------------------------- #
@app.get("/monitor/tick")
@app.post("/monitor/tick")
def monitor_tick(key: str = "", force: bool = False):
    """Corre UNA pasada del monitor. Protegido por clave (env MONITOR_TICK_KEY).

    - `key`: debe coincidir con MONITOR_TICK_KEY, si no, 403.
    - `force=true`: ignora el horario y fuerza alertas (solo para pruebas).
    Fuera de horario de mercado no hace nada (salvo force), para no gastar.
    """
    expected = os.getenv("MONITOR_TICK_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="MONITOR_TICK_KEY no configurada en el servidor.")
    if not secrets.compare_digest(key, expected):
        raise HTTPException(status_code=403, detail="Clave inválida.")

    market_open = is_market_open()
    if not market_open and not force:
        return {"ran": False, "market_open": False, "note": "mercado cerrado; no se hizo nada."}

    try:
        check_once(force=force)
    except Exception as exc:  # noqa: BLE001  (no tumbar el endpoint por un fallo de datos)
        raise HTTPException(status_code=500, detail=f"Fallo en la pasada del monitor: {exc}") from exc
    return {"ran": True, "market_open": market_open, "forced": force}


@app.get("/watchlist")
def list_watchlist():
    return watchlist.get_watchlist()


@app.get("/watchlist/status")
def watchlist_status():
    """Estado compacto de cada ticker de la watchlist (para los chips).

    Analiza cada uno (GRATIS, sin IA). Resistente a fallos: un ticker que falle
    no tumba al resto. Puede tardar unos segundos si la lista es larga.
    """
    out = []
    for t in watchlist.get_watchlist():
        try:
            r = analyze_ticker(t)
            out.append(
                {
                    "ticker": r.ticker,
                    "classification": r.classification,
                    "trend": r.trend,
                    "price": r.price,
                    "distance_from_open_pct": r.distance_from_open_pct,
                    "error": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            out.append(
                {
                    "ticker": t.upper().strip(),
                    "classification": None,
                    "trend": None,
                    "price": None,
                    "distance_from_open_pct": None,
                    "error": str(exc),
                }
            )
    return out


@app.post("/watchlist/{ticker}")
def add_to_watchlist(ticker: str):
    return watchlist.add_ticker(ticker)


@app.delete("/watchlist/{ticker}")
def remove_from_watchlist(ticker: str):
    return watchlist.remove_ticker(ticker)


# --------------------------------------------------------------------------- #
#  Diario de decisiones (registro manual, NO ejecuta ordenes)
# --------------------------------------------------------------------------- #
class JournalEntryIn(BaseModel):
    ticker: str
    decision: str  # CALL | PUT | ESPERAR
    price: float = 0.0
    note: str = ""
    context: dict = {}
    contract: dict | None = None  # {type, strike, expiry, entry_premium, stop?} para seguimiento de salida


class OutcomeIn(BaseModel):
    outcome: str  # en_curso | acierto | fallo | neutra


@app.get("/journal")
def list_journal():
    return journal.get_journal()


@app.get("/journal/stats")
def journal_statistics():
    """Estadísticas del diario por conteo (win-rate, rachas, por ticker, por hora).
    GRATIS, sin IA, solo lectura. No ejecuta órdenes."""
    return journal_stats()


@app.post("/journal")
def create_journal_entry(entry: JournalEntryIn):
    try:
        return journal.add_entry(
            entry.ticker,
            entry.decision,
            entry.price,
            entry.note,
            entry.context,
            entry.contract,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/positions")
def positions():
    """Posiciones abiertas del diario con su señal de salida (+15/+20/+30%, defensa,
    tesis invalidada). GRATIS, sin IA. Lee la prima actual de la cadena. Solo avisa."""
    return open_positions_status()


@app.patch("/journal/{entry_id}")
def update_journal_outcome(entry_id: str, body: OutcomeIn):
    try:
        updated = journal.set_outcome(entry_id, body.outcome)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    return updated


@app.delete("/journal/{entry_id}")
def delete_journal_entry(entry_id: str):
    return journal.delete_entry(entry_id)


# --------------------------------------------------------------------------- #
#  Track record de señales automáticas (anota el monitor, verifica el cron)
# --------------------------------------------------------------------------- #
@app.get("/signals-log")
def signals_log_list():
    """Registro de señales CALL/PUT enviadas y su resultado (acierto/fallo).
    GRATIS, solo lectura. No ejecuta órdenes."""
    return {"stats": signals_log.stats(), "signals": signals_log.get_log()}


@app.post("/signals-log/review")
def signals_log_review():
    """Verifica las señales abiertas (target1 vs stop) y persiste resultados.
    Pensado para un cron diario; también disparable a mano. Solo lectura de mercado."""
    return signals_log.review_open_signals()
