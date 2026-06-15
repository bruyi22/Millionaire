@echo off
REM ===================================================================
REM  Millionaire - arranque unico
REM  Levanta los 3 procesos en ventanas separadas:
REM    1) Backend  (API FastAPI)      -> http://127.0.0.1:8000
REM    2) Monitor  (alertas Telegram) -> solo alerta en horario NYSE
REM    3) Frontend (web Vite)         -> http://localhost:5173
REM  Cierra cada ventana para detener ESE proceso.
REM  SOLO analisis/monitoreo: NUNCA ejecuta ordenes en el broker.
REM ===================================================================

REM Nos situamos en la carpeta de este .bat (la raiz del proyecto).
cd /d "%~dp0"

echo.
echo  Iniciando Millionaire...
echo    - Backend  : http://127.0.0.1:8000
echo    - Frontend : http://localhost:5173
echo    - Monitor  : alertas a Telegram (solo en horario de mercado)
echo.

start "Millionaire - Backend (API)" cmd /k "cd backend && set PYTHONUTF8=1 && .venv\Scripts\python.exe -m uvicorn server.main:app --port 8000"

start "Millionaire - Monitor (alertas)" cmd /k "cd backend && set PYTHONUTF8=1 && .venv\Scripts\python.exe run_monitor.py"

start "Millionaire - Frontend (web)" cmd /k "cd frontend && npm run dev"

echo  Listo. Se abrieron 3 ventanas.
echo  Abre http://localhost:5173 en tu navegador.
echo  Para detener todo, cierra las 3 ventanas.
echo.
pause
