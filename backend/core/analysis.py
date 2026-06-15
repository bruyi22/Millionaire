"""
FASE 1 - Motor matematico de analisis tecnico.

Responsabilidad:
  1. Descargar datos historicos del ticker (yfinance).
  2. Calcular indicadores (RSI, MACD, SMAs, Volumen, ATR) con pandas-ta.
  3. Medir la distancia desde la apertura del dia (movimiento extendido).
  4. Encender banderas de advertencia tipo "Risk Manager ultra-conservador".

NO ejecuta ordenes. Solo analiza y devuelve un diccionario de datos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf


# --------------------------------------------------------------------------- #
#  Estructura de resultado
# --------------------------------------------------------------------------- #
@dataclass
class AnalysisResult:
    ticker: str
    price: float
    day_open: float
    prev_close: float
    distance_from_open_pct: float      # % de movimiento intradia desde la apertura
    day_range_pct: float               # rango del dia (high-low) como % del precio
    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    sma20: float
    sma50: float
    sma200: float
    volume: float
    avg_volume20: float
    volume_ratio: float                # volumen de hoy / promedio 20d
    atr: float
    atr_pct: float                     # ATR como % del precio (volatilidad tipica)
    flags: list[str] = field(default_factory=list)   # banderas de advertencia
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    classification: str = "Media"      # Alta | Media | Riesgosa
    trend: str = "Lateral"             # Alcista | Bajista | Lateral


# --------------------------------------------------------------------------- #
#  Utilidades
# --------------------------------------------------------------------------- #
def _safe(value) -> float:
    """Convierte a float y evita NaN (devuelve 0.0 si no hay dato)."""
    try:
        v = float(value)
        return 0.0 if math.isnan(v) else v
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------- #
#  Indicadores tecnicos (pandas puro, sin librerias externas)
# --------------------------------------------------------------------------- #
def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """RSI con suavizado de Wilder (estandar de la industria)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Devuelve (linea MACD, linea de senal, histograma)."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Average True Range con suavizado de Wilder (mide volatilidad tipica)."""
    prev_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()


# --------------------------------------------------------------------------- #
#  Funcion principal
# --------------------------------------------------------------------------- #
def analyze_ticker(ticker: str) -> AnalysisResult:
    ticker = ticker.upper().strip()

    # 1) Datos diarios (1 año: suficiente para calcular SMA200 con margen)
    df = yf.Ticker(ticker).history(period="1y", interval="1d")
    # yfinance a veces devuelve una vela parcial/vacia (OHLC en NaN) en pre-market
    # o por huecos del proveedor. La descartamos para no tomar precio 0 ni
    # envenenar las SMAs con NaN.
    df = df[df["Close"].notna()]
    if df.empty or len(df) < 30:
        raise ValueError(
            f"No hay suficientes datos para '{ticker}'. "
            "Revisa que el simbolo sea valido."
        )

    # 2) Indicadores tecnicos (calculados con pandas puro)
    df["RSI"] = rsi(df["Close"], length=14)
    macd_line, macd_signal, macd_hist = macd(df["Close"], fast=12, slow=26, signal=9)
    df["MACD"] = macd_line
    df["MACD_signal"] = macd_signal
    df["MACD_hist"] = macd_hist
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=200).mean()
    df["ATR"] = atr(df["High"], df["Low"], df["Close"], length=14)
    df["VOL_SMA20"] = df["Volume"].rolling(window=20).mean()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = _safe(last["Close"])
    day_open = _safe(last["Open"])
    prev_close = _safe(prev["Close"])
    atr_val = _safe(last["ATR"])

    distance_from_open_pct = ((price - day_open) / day_open * 100) if day_open else 0.0
    day_range_pct = ((last["High"] - last["Low"]) / price * 100) if price else 0.0
    atr_pct = (atr_val / price * 100) if price else 0.0
    avg_volume20 = _safe(last["VOL_SMA20"])
    volume = _safe(last["Volume"])
    volume_ratio = (volume / avg_volume20) if avg_volume20 else 0.0

    result = AnalysisResult(
        ticker=ticker,
        price=round(price, 2),
        day_open=round(day_open, 2),
        prev_close=round(prev_close, 2),
        distance_from_open_pct=round(distance_from_open_pct, 2),
        day_range_pct=round(day_range_pct, 2),
        rsi=round(_safe(last["RSI"]), 2),
        macd=round(_safe(last["MACD"]), 4),
        macd_signal=round(_safe(last["MACD_signal"]), 4),
        macd_hist=round(_safe(last["MACD_hist"]), 4),
        sma20=round(_safe(last["SMA20"]), 2),
        sma50=round(_safe(last["SMA50"]), 2),
        sma200=round(_safe(last["SMA200"]), 2),
        volume=volume,
        avg_volume20=avg_volume20,
        volume_ratio=round(volume_ratio, 2),
        atr=round(atr_val, 2),
        atr_pct=round(atr_pct, 2),
    )

    _evaluate_risk(result)
    return result


# --------------------------------------------------------------------------- #
#  Serie historica de precios (para el grafico del frontend)
# --------------------------------------------------------------------------- #
def price_history(ticker: str, period: str = "6mo") -> list[dict]:
    """Devuelve la serie de cierres + medias moviles para dibujar el grafico.

    Solo lectura: no calcula banderas ni veredictos, solo precios.
    `period` acepta los valores de yfinance: '1mo', '3mo', '6mo', '1y', etc.
    """
    ticker = ticker.upper().strip()
    df = yf.Ticker(ticker).history(period=period, interval="1d")
    df = df[df["Close"].notna()]  # descartar velas parciales/vacias (NaN)
    if df.empty:
        raise ValueError(
            f"No hay datos historicos para '{ticker}'. Revisa el simbolo."
        )

    # Medias moviles sobre la ventana pedida (mismas que el analisis).
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()

    out: list[dict] = []
    for idx, row in df.iterrows():
        out.append(
            {
                "date": idx.strftime("%Y-%m-%d"),
                "close": round(_safe(row["Close"]), 2),
                "sma20": round(_safe(row["SMA20"]), 2) or None,
                "sma50": round(_safe(row["SMA50"]), 2) or None,
            }
        )
    return out


# --------------------------------------------------------------------------- #
#  Firma de senales (para detectar cambios relevantes en el monitoreo)
# --------------------------------------------------------------------------- #
def signal_signature(r: AnalysisResult) -> dict:
    """Resume el estado tecnico en categorias. Si esta firma cambia entre dos
    revisiones, significa que paso algo RELEVANTE y vale la pena re-alertar."""
    if r.rsi >= 70:
        rsi_zone = "sobrecompra"
    elif r.rsi <= 30:
        rsi_zone = "sobreventa"
    else:
        rsi_zone = "neutral"

    if r.macd > r.macd_signal:
        macd_dir = "alcista"
    elif r.macd < r.macd_signal:
        macd_dir = "bajista"
    else:
        macd_dir = "plano"

    extended = bool(r.atr_pct > 0 and abs(r.distance_from_open_pct) > r.atr_pct)

    return {
        "trend": r.trend,
        "classification": r.classification,
        "rsi_zone": rsi_zone,
        "macd_dir": macd_dir,
        "extended": extended,
    }


# --------------------------------------------------------------------------- #
#  Logica del Risk Manager ultra-conservador
# --------------------------------------------------------------------------- #
def _evaluate_risk(r: AnalysisResult) -> None:
    """Aplica reglas conservadoras: NO perseguir el precio, esperar pullbacks."""

    # --- Tendencia segun medias moviles ---
    if r.price > r.sma50 > r.sma200:
        r.trend = "Alcista"
        r.pros.append("Tendencia alcista (precio > SMA50 > SMA200)")
    elif r.price < r.sma50 < r.sma200:
        r.trend = "Bajista"
        r.cons.append("Tendencia bajista (precio < SMA50 < SMA200)")
    else:
        r.trend = "Lateral"
        r.cons.append("Sin tendencia clara (medias entrelazadas)")

    # --- RSI: extremos = esperar retroceso ---
    if r.rsi >= 70:
        r.flags.append(f"RSI sobrecomprado ({r.rsi}). Riesgo de perseguir el precio.")
        r.cons.append("RSI en zona de sobrecompra: esperar pullback antes de CALLS.")
    elif r.rsi <= 30:
        r.flags.append(f"RSI sobrevendido ({r.rsi}). Posible rebote, pero cuchillo cayendo.")
        r.cons.append("RSI en sobreventa: no atrapar cuchillos; esperar confirmacion.")
    elif 45 <= r.rsi <= 60:
        r.pros.append(f"RSI neutral-saludable ({r.rsi}): margen para moverse.")

    # --- MACD: momentum ---
    if r.macd > r.macd_signal and r.macd_hist > 0:
        r.pros.append("MACD con momentum alcista (linea sobre senal).")
    elif r.macd < r.macd_signal and r.macd_hist < 0:
        r.cons.append("MACD con momentum bajista (linea bajo senal).")

    # --- Movimiento extendido: la regla central de "no perseguir" ---
    # Si el movimiento intradia ya supera la volatilidad tipica (ATR%), esta extendido.
    if r.atr_pct > 0 and abs(r.distance_from_open_pct) > r.atr_pct:
        direccion = "subida" if r.distance_from_open_pct > 0 else "caida"
        r.flags.append(
            f"Movimiento EXTENDIDO: {direccion} de {abs(r.distance_from_open_pct)}% "
            f"hoy supera el ATR diario ({r.atr_pct}%). Esperar retroceso."
        )
        r.cons.append("Precio extendido respecto a su rango normal: alto riesgo de entrar tarde.")
    else:
        r.pros.append("Movimiento intradia dentro del rango normal (no extendido).")

    # --- Volumen: confirma o desmiente el movimiento ---
    if r.volume_ratio >= 1.5:
        r.pros.append(f"Volumen fuerte ({r.volume_ratio}x el promedio): convicción real.")
    elif 0 < r.volume_ratio < 0.7:
        r.cons.append(f"Volumen flojo ({r.volume_ratio}x promedio): movimiento poco fiable.")

    # --- Clasificacion final de la oportunidad ---
    n_flags = len(r.flags)
    if n_flags == 0 and len(r.pros) >= 3 and r.trend == "Alcista":
        r.classification = "Alta"
    elif n_flags >= 2 or r.trend == "Bajista":
        r.classification = "Riesgosa"
    else:
        r.classification = "Media"
