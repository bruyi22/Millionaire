"""
FASE 5 - Analisis de la cadena de opciones (calls/puts).

Responsabilidad:
  1. Bajar la cadena de opciones del ticker (yfinance).
  2. Quedarse con los strikes CERCA DEL DINERO (los relevantes).
  3. Aplicar el "lente Risk Manager": marcar contratos peligrosos
     (spread ancho, poca liquidez, IV muy alta).

NO ejecuta ordenes ni recomienda comprar. Solo describe y advierte.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from statistics import NormalDist

import yfinance as yf


# --------------------------------------------------------------------------- #
#  Umbrales del Risk Manager (conservadores). Editar aqui si quieres calibrar.
# --------------------------------------------------------------------------- #
SPREAD_PCT_WARN = 10.0       # spread bid/ask > 10% del precio medio = caro de entrar/salir
OPEN_INTEREST_WARN = 100     # open interest < 100 contratos = iliquido
VOLUME_WARN = 10             # volumen del dia < 10 = poco interes hoy
IV_WARN = 80.0               # IV > 80% = prima muy cara / riesgo de IV crush

# Tasa libre de riesgo anual aproximada para el modelo Black-Scholes (editable).
# Poco sensible en vencimientos cortos; ~4% es razonable para el entorno actual.
RISK_FREE_RATE = 0.04

_N = NormalDist()  # Normal estandar: .cdf() y .pdf() para los Greeks


def _safe(value) -> float:
    try:
        v = float(value)
        return 0.0 if math.isnan(v) else v
    except (TypeError, ValueError):
        return 0.0


# --------------------------------------------------------------------------- #
#  Break-even y Greeks (calculo propio: yfinance NO los entrega)
# --------------------------------------------------------------------------- #
def _break_even(kind: str, strike: float, premium: float) -> float:
    """Precio del subyacente al que el contrato 'empata' (ni gana ni pierde).

    Call: hay que superar strike + prima. Put: hay que bajar de strike - prima.
    """
    return strike + premium if kind == "call" else strike - premium


def _black_scholes_greeks(
    kind: str, S: float, K: float, T: float, sigma: float, r: float = RISK_FREE_RATE
) -> dict:
    """Greeks por Black-Scholes. T en años, sigma en fraccion (0.45 = 45% IV).

    delta: sensibilidad al precio del subyacente (por $1).
    gamma: cuanto cambia delta por $1 de movimiento.
    theta: perdida de valor por el paso de UN dia (ya dividido /365).
    vega : cambio de prima por +1% de IV (ya dividido /100).
    Si faltan datos fiables (T<=0, sigma<=0, precios<=0) devuelve ceros.
    """
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    sqrt_t = math.sqrt(T)
    d1 = (math.log(S / K) + (r + sigma * sigma / 2) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    pdf_d1 = _N.pdf(d1)
    discount = math.exp(-r * T)

    if kind == "call":
        delta = _N.cdf(d1)
        theta = -(S * pdf_d1 * sigma) / (2 * sqrt_t) - r * K * discount * _N.cdf(d2)
    else:
        delta = _N.cdf(d1) - 1.0
        theta = -(S * pdf_d1 * sigma) / (2 * sqrt_t) + r * K * discount * _N.cdf(-d2)

    gamma = pdf_d1 / (S * sigma * sqrt_t)
    vega = S * pdf_d1 * sqrt_t

    return {
        "delta": round(delta, 3),
        "gamma": round(gamma, 4),
        "theta": round(theta / 365.0, 3),  # por dia calendario
        "vega": round(vega / 100.0, 3),    # por +1% de IV
    }


def _underlying_price(tk: yf.Ticker) -> float:
    """Ultimo cierre del subyacente (para ubicar el dinero / ATM)."""
    hist = tk.history(period="5d", interval="1d")
    hist = hist[hist["Close"].notna()]  # descartar velas parciales/vacias (NaN)
    if hist.empty:
        return 0.0
    return _safe(hist["Close"].iloc[-1])


def _evaluate_contract(c: dict) -> list[str]:
    """Banderas de riesgo para un contrato individual."""
    flags: list[str] = []
    if c["spread_pct"] > SPREAD_PCT_WARN:
        flags.append(
            f"Spread ancho ({c['spread_pct']}%): el mercado te come la prima al entrar/salir."
        )
    if c["open_interest"] < OPEN_INTEREST_WARN:
        flags.append(
            f"Open interest bajo ({c['open_interest']}): iliquido, dificil de salir."
        )
    if c["volume"] < VOLUME_WARN:
        flags.append(f"Volumen flojo hoy ({c['volume']}): poco interes en el dia.")
    if c["iv"] > IV_WARN:
        flags.append(
            f"IV muy alta ({c['iv']}%): prima cara y riesgo de IV crush aunque aciertes."
        )
    return flags


def _row_to_contract(row, kind: str, underlying: float, dte: int | None) -> dict:
    strike = _safe(row.get("strike"))
    bid = _safe(row.get("bid"))
    ask = _safe(row.get("ask"))
    mid = (bid + ask) / 2 if (bid and ask) else _safe(row.get("lastPrice"))
    spread_pct = ((ask - bid) / mid * 100) if mid else 0.0
    iv = _safe(row.get("impliedVolatility")) * 100  # yfinance la da en fraccion

    # Break-even: usamos la prima media (mid) como costo estimado de entrada.
    premium = mid if mid else _safe(row.get("lastPrice"))
    break_even = _break_even(kind, strike, premium)
    be_move_pct = (break_even - underlying) / underlying * 100 if underlying else 0.0

    # Greeks por Black-Scholes con la IV del propio contrato.
    years = dte / 365.0 if dte and dte > 0 else 0.0
    greeks = _black_scholes_greeks(kind, underlying, strike, years, iv / 100.0)

    contract = {
        "type": kind,                       # "call" | "put"
        "strike": round(strike, 2),
        "last": round(_safe(row.get("lastPrice")), 2),
        "bid": round(bid, 2),
        "ask": round(ask, 2),
        "mid": round(mid, 2),
        "spread_pct": round(spread_pct, 1),
        "volume": int(_safe(row.get("volume"))),
        "open_interest": int(_safe(row.get("openInterest"))),
        "iv": round(iv, 1),
        "in_the_money": bool(row.get("inTheMoney", False)),
        "moneyness_pct": round((strike - underlying) / underlying * 100, 1)
        if underlying
        else 0.0,
        "break_even": round(break_even, 2),
        "break_even_move_pct": round(be_move_pct, 1),
        "delta": greeks["delta"],
        "gamma": greeks["gamma"],
        "theta": greeks["theta"],
        "vega": greeks["vega"],
    }
    contract["flags"] = _evaluate_contract(contract)
    return contract


def _near_the_money(
    df, underlying: float, kind: str, n: int, dte: int | None
) -> list[dict]:
    """Toma los n strikes mas cercanos al precio del subyacente (a cada lado)."""
    if df.empty or not underlying:
        return []
    df = df.copy()
    df["__dist"] = (df["strike"] - underlying).abs()
    nearest = df.nsmallest(n * 2, "__dist").sort_values("strike")
    return [_row_to_contract(row, kind, underlying, dte) for _, row in nearest.iterrows()]


# --------------------------------------------------------------------------- #
#  Movimiento esperado (Expected Move): cuanto "paga" el mercado que se mueva
#  el subyacente hasta el vencimiento. Es el lente correcto para juzgar si el
#  movimiento al break-even de un contrato es realista o pide demasiado.
# --------------------------------------------------------------------------- #
def _expected_move(
    calls: list[dict], puts: list[dict], underlying: float, dte: int | None
) -> dict | None:
    """Movimiento esperado (1 sigma, ~68%) hasta el vencimiento.

    Metodo principal: STRADDLE ATM (prima call ATM + prima put ATM) en el strike
    comun mas cercano al dinero. Es la estimacion que el mercado esta cotizando.
    Fallback: formula por IV  EM = S * IV_atm * sqrt(DTE/365)  si faltan primas.
    Devuelve {expected_move (USD), expected_move_pct, method} o None si no se puede.
    """
    if not underlying or not calls or not puts:
        return None

    call_by_strike = {c["strike"]: c for c in calls}
    put_by_strike = {p["strike"]: p for p in puts}
    common = sorted(
        set(call_by_strike) & set(put_by_strike), key=lambda k: abs(k - underlying)
    )

    em: float | None = None
    method = "straddle"
    if common:
        k = common[0]
        cm = call_by_strike[k]["mid"]
        pm = put_by_strike[k]["mid"]
        if cm > 0 and pm > 0:
            em = cm + pm

    # Fallback por IV del call mas cercano al dinero.
    if em is None:
        atm_call = min(calls, key=lambda c: abs(c["strike"] - underlying))
        iv = _safe(atm_call.get("iv")) / 100.0  # iv viene en % en el contrato
        years = dte / 365.0 if dte and dte > 0 else 1 / 365.0  # 0DTE -> ~1 dia
        if iv > 0:
            em = underlying * iv * math.sqrt(years)
            method = "iv"

    if not em or em <= 0:
        return None

    return {
        "expected_move": round(em, 2),
        "expected_move_pct": round(em / underlying * 100, 2),
        "method": method,
    }


def _attach_be_em_ratio(contracts: list[dict], em_pct: float | None) -> None:
    """Adjunta a cada contrato `be_em_ratio` = |mov. al break-even| / mov. esperado.

    < 1 = el break-even cae DENTRO de lo que el mercado espera (favorable);
    > 1 = el contrato necesita MAS movimiento del que el mercado cotiza (caro).
    """
    for c in contracts:
        if em_pct and em_pct > 0:
            c["be_em_ratio"] = round(abs(c["break_even_move_pct"]) / em_pct, 2)
        else:
            c["be_em_ratio"] = None


def option_chain_analysis(
    ticker: str, expiry: str | None = None, n_strikes: int = 6
) -> dict:
    """Analiza la cadena de opciones cerca del dinero para un vencimiento.

    Si `expiry` es None, usa el vencimiento mas cercano disponible.
    """
    ticker = ticker.upper().strip()
    tk = yf.Ticker(ticker)

    expiries = list(tk.options)
    if not expiries:
        raise ValueError(f"'{ticker}' no tiene opciones listadas (o no hay datos).")

    if expiry is None:
        expiry = expiries[0]
    elif expiry not in expiries:
        raise ValueError(
            f"Vencimiento '{expiry}' no disponible para {ticker}. "
            f"Opciones: {', '.join(expiries[:8])}..."
        )

    underlying = _underlying_price(tk)
    chain = tk.option_chain(expiry)

    # Dias hasta el vencimiento (DTE): clave para theta / Greeks / tiempo restante.
    try:
        dte = (datetime.strptime(expiry, "%Y-%m-%d").date() - date.today()).days
    except ValueError:
        dte = None

    calls = _near_the_money(chain.calls, underlying, "call", n_strikes, dte)
    puts = _near_the_money(chain.puts, underlying, "put", n_strikes, dte)

    # Movimiento esperado del vencimiento y ratio break-even/esperado por contrato.
    em = _expected_move(calls, puts, underlying, dte)
    em_pct = em["expected_move_pct"] if em else None
    _attach_be_em_ratio(calls, em_pct)
    _attach_be_em_ratio(puts, em_pct)

    return {
        "ticker": ticker,
        "underlying_price": round(underlying, 2),
        "expiry": expiry,
        "dte": dte,
        "available_expiries": expiries,
        "expected_move": em["expected_move"] if em else None,
        "expected_move_pct": em_pct,
        "em_method": em["method"] if em else None,
        "calls": calls,
        "puts": puts,
    }
