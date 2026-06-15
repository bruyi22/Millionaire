"""
FASE 3 - Arranque del bucle de monitoreo.

Uso:
    python run_monitor.py           # bucle continuo (respeta horario de mercado)
    python run_monitor.py once      # UNA pasada inmediata, ignora horario (para probar)

El intervalo se configura con CHECK_INTERVAL_SECONDS en .env (default 300s = 5 min).
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
    from server.monitor import check_once, run_loop

    if len(sys.argv) > 1 and sys.argv[1].lower() == "once":
        print("▶️  Modo prueba: una pasada inmediata (ignora horario de mercado).\n")
        check_once(force=True)
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
