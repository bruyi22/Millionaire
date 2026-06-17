"""
FASE 1 - Cliente de Telegram.

Envia mensajes de texto en formato Markdown (legacy) usando la Bot API.
No requiere librerias externas mas alla de 'requests'.
"""

from __future__ import annotations

import os

import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(text: str) -> dict:
    """Envia un mensaje a tu chat de Telegram. Devuelve la respuesta JSON."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise RuntimeError(
            "Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en tu archivo .env"
        )

    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, data=payload, timeout=15)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram rechazo el mensaje: {data}")
    return data


# --------------------------------------------------------------------------- #
#  Alerta corta de CRUCE DE NIVEL (disparador intradia)
# --------------------------------------------------------------------------- #
def format_level_alert(
    ticker: str, level: str, level_price: float, current: float, direction: str
) -> str:
    """Mensaje corto y directo cuando el precio cruza un nivel disparador.

    `direction`: "up" (rompe hacia arriba, sesgo CALL) o "down" (pierde, sesgo PUT).
    """
    if direction == "up":
        icono, verbo, sesgo = "🚀", "rompio", "sesgo CALL"
    else:
        icono, verbo, sesgo = "🔻", "perdio", "sesgo PUT"

    return "\n".join(
        [
            f"📍 *[NIVEL]* {icono} *{ticker}* {verbo} *{level}* `${level_price}`",
            f"Precio ahora: `${current}`  ({sesgo})",
            "",
            "⚠️ *Esto NO es una señal de compra.* Es solo un aviso de que el",
            "precio cruzó una línea clave. Espera una *SEÑAL CALL/PUT* (con",
            "entrada/stop/objetivo) para tener una operación con ventaja.",
        ]
    )


# --------------------------------------------------------------------------- #
#  Alerta del PLAYBOOK INTRADÍA (momentum 5 min) — respaldo "por si no miro"
#  OJO: el feed va atrasado; el mensaje obliga a verificar el precio en vivo.
# --------------------------------------------------------------------------- #
def format_playbook_alert(pb: dict) -> str:
    """Aviso de Telegram cuando el playbook intradía marca una entrada accionable.

    Solo se manda para veredictos de COMPRAR (reclaim/ruptura). Como el feed
    tiene atraso, el mensaje recuerda mirar el precio EN VIVO del bróker y no
    perseguir si ya se alejó del entry. No es orden automática: tú ejecutas.
    """
    ticker = pb.get("ticker", "?")
    price = pb.get("current_price")
    verdict = pb.get("verdict", {})
    head = verdict.get("headline", "")
    detail = verdict.get("detail", "")
    ind = pb.get("indicators", {})
    candle_time = pb.get("candle_time", "?")

    return "\n".join(
        [
            f"⚡ *[INTRADÍA]* *{ticker}* — {head}",
            f"💵 Precio (última vela {candle_time}): `${price}`",
            f"VWAP `${ind.get('vwap')}` · EMA9 `${ind.get('ema9')}` · "
            f"RSI `{ind.get('rsi')}` · Vol x`{ind.get('rel_volume')}`",
            "",
            f"🎯 {detail}",
            "",
            "⚠️ *El feed va atrasado.* Mira el precio EN VIVO de tu bróker:",
            "si sigue cerca del plan, entra con límite; si ya se disparó",
            "lejos, NO lo persigas. Tú decides y ejecutas.",
        ]
    )


# --------------------------------------------------------------------------- #
#  Alerta DIRECTA de señal CALL / PUT / NO OPERAR  (motor decision_signal)
#  Es la alerta PRINCIPAL: corta, accionable, 100% determinista (sin IA).
# --------------------------------------------------------------------------- #
def format_signal_alert(sig: dict) -> str:
    """Mensaje directo de entrada a partir de core.signal.decision_signal().

    - CALL/PUT: dirección + entrada/stop/objetivos + R:R + contrato + confianza.
    - NO OPERAR: aviso corto de que se cerró la ventaja (tesis sin ventaja).
    Sin IA, sin coste. Footer recuerda que tú decides y ejecutas.
    """
    ticker = sig.get("ticker", "?")
    signal = sig.get("signal", "NO OPERAR")
    price = sig.get("price")
    conf = sig.get("confidence", 0)

    # Caso NO OPERAR: aviso corto (la ventaja se cerró o no hay confluencia).
    if signal == "NO OPERAR":
        motivo = sig.get("veto_reason") or sig.get("reason") or "sin ventaja clara."
        return "\n".join(
            [
                f"⚪ *{ticker}* — *NO OPERAR*",
                f"Precio: `${price}`",
                f"Motivo: {motivo}",
                "_Sin ventaja ahora · tú decides y ejecutas_",
            ]
        )

    # Caso CALL / PUT: señal accionable con plan.
    icono = "🟢" if signal == "CALL" else "🔴"
    plan = sig.get("plan") or {}
    lines: list[str] = [
        f"{icono} *{ticker}* — SEÑAL *{signal}*  (confianza `{conf}%`)",
        f"💵 Precio: `${price}`",
        "",
        "🎯 *Plan*",
        f"• Entrada: `${plan.get('entry')}`",
        f"• Stop: `${plan.get('stop')}`",
        f"• Objetivo 1: `${plan.get('target1')}`",
        f"• Objetivo 2: `${plan.get('target2')}`",
        f"• R:R: `{plan.get('rr')}`",
    ]

    contract = sig.get("contract_hint")
    if contract:
        lines += ["", f"🎟️ *Contrato:* {contract}"]

    reason = sig.get("reason")
    if reason:
        lines += ["", f"🧭 {reason}"]

    risk = sig.get("risk")
    if risk:
        lines += [f"🛡️ {risk}"]

    lines += ["", "———", "_Solo soporte de decisión · tú decides y ejecutas_"]
    return "\n".join(lines)


