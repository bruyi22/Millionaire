"""
FASE 3 - Arranque del bucle de monitoreo.

Uso:
    python run_monitor.py           # bucle continuo (respeta horario de mercado)
    python run_monitor.py once      # UNA pasada inmediata, FORZADA, ignora horario (prueba)
    python run_monitor.py tick      # UNA pasada para el cron: solo si el mercado está
                                    #   abierto y SIN forzar (respeta cambios/cooldowns)

El modo `tick` es el que ejecuta GitHub Actions: una sola pasada y termina. Si el
mercado está cerrado no hace nada (ahorra minutos de Actions en feriados).

El intervalo (modo bucle) se configura con CHECK_INTERVAL_SECONDS en .env (default 300s).
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

# La consola de Windows usa cp1252 por defecto y revienta al imprimir emojis.
# Forzamos UTF-8 en stdout/stderr para que un simple print no mate el monitor.
for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8")


def main() -> None:
    load_dotenv()

    # Importamos despues de load_dotenv para que las claves esten disponibles
    from server.monitor import check_once, is_market_open, run_loop

    arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""

    if arg == "once":
        print("▶️  Modo prueba: una pasada inmediata FORZADA (ignora horario).\n")
        check_once(force=True)
        return

    if arg == "tick":
        # Modo cron (GitHub Actions): una sola pasada, sin forzar, solo si abre.
        if is_market_open():
            print("▶️  Tick: mercado abierto, revisando watchlist.\n")
            check_once(force=False)
        else:
            print("⏸️  Tick: mercado cerrado, no hago nada.")
        return

    interval = int(os.getenv("CHECK_INTERVAL_SECONDS", "300"))
    run_loop(interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Monitor detenido por el usuario.")
    except Exception as exc:  # noqa: BLE001
        print(f"\n❌ Error: {exc}")
        sys.exit(1)
