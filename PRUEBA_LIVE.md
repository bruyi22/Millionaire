# 🧪 Checklist de prueba LIVE (mercado abierto)

> Todo se ha validado con el mercado **cerrado** (las señales salían "NO OPERAR" por
> el veto de horario) o con datos sintéticos. Esta es la prueba real, de punta a punta,
> en horario **NYSE: 9:30–16:00 hora de Nueva York (ET)** un día entre semana.
>
> **Recordatorio:** la herramienta es SOLO análisis y soporte de decisión. NUNCA ejecuta
> órdenes. Si "abres una posición" aquí es para registrarla en el diario y seguirla; tú
> decides y ejecutas en tu bróker (o haz la prueba en papel, sin dinero real).
>
> Marca cada casilla `[x]` y apunta lo que veas raro en la sección **Hallazgos** del final.

---

## 0) Antes de abrir (llega 10-15 min antes de las 9:30 ET)

- [ ] Arranca todo con `iniciar.bat` (doble clic). Deben abrirse **3 ventanas**: Backend, Monitor, Frontend.
- [ ] Backend: la ventana no muestra errores rojos; dice `Uvicorn running on http://127.0.0.1:8000`.
- [ ] Monitor: arranca sin reventar (el fix UTF-8 evita el cuelgue por emojis).
- [ ] Frontend: abre el navegador en `http://localhost:5173`.
- [ ] La página carga sin pantalla en blanco. Abre la consola del navegador (F12) y déjala visible: **0 errores** durante toda la prueba.
- [ ] **Régimen de mercado** (banner arriba del todo): antes de las 9:30 sigue en ⚪ **NO OPERAR · "Mercado cerrado"**. Correcto.

---

## 1) Apertura — 9:30 a 10:00 ET (lo más sensible al tiempo)

> Este es el único módulo que SOLO se puede probar bien en esta franja. No te la pierdas.

- [ ] **9:30:** el banner de régimen cambia de "Mercado cerrado" a un régimen real (🟢 ALCISTA / 🔴 BAJISTA / 🟡 MIXTO) con score, VIX y desglose. Pulsa 🔄 si tarda.
- [ ] Carga 2-3 tickers líquidos de tu watchlist (ej. NVDA, AAPL, SPY-equivalente).
- [ ] **Módulo de apertura** de cada uno:
  - [ ] **9:30–9:45** → fase **OBSERVAR** (señal OBSERVAR, "la 1ª vela informa, no decide").
  - [ ] **9:45–10:00** → fase **CONFIRMANDO** (señal ESPERAR).
  - [ ] **10:00+** → fase **DECISIÓN** (CALL / PUT / NO OPERAR).
  - [ ] El **rango de apertura** (máx/mín 9:30–9:45) tiene números razonables.
  - [ ] El **VWAP** y el "precio sobre/bajo VWAP" coinciden con lo que ves en el gráfico.
  - [ ] El **hueco** (gap %) y el sesgo premarket cuadran con cómo abrió.
  - [ ] El **"relato del día"** (chips →) se va llenando con eventos coherentes (recuperó VWAP, rompió máx con volumen, shakeout…).
- [ ] **Gráfico de velas intradía**: las velas 5m se dibujan, el eje muestra la hora ET correcta, y las líneas de niveles (R2/R1/Pivot/S1/S2) están etiquetadas.
- [ ] **Auto-refresco 30s**: el sello "Actualizado HH:MM:SS" avanza solo cada ~30s sin recargar la página. Prueba el toggle Auto/Pausado.

---

## 2) Media sesión — 10:00 a 15:30 ET (el grueso de los módulos)

### Señal estructurada (CALL/PUT/NO OPERAR)
- [ ] Con el mercado abierto, al menos un ticker da una señal **distinta de "NO OPERAR"** (o si todos vetan, que el motivo sea lógico: baja confianza/contradicción, no un bug).
- [ ] Cuando hay señal, aparece el **plan**: Entrada / Stop / Target1 / Target2 / **R:R**. Verifica que los niveles son coherentes (entrada cerca del precio, stop al otro lado, R:R ≥ 1).
- [ ] La tabla **"cómo votó cada factor"** tiene sentido (tendencia, VWAP, apertura, régimen, MACD, RSI…).

### Contrato recomendado
- [ ] En un ticker con señal, abre el panel de opciones y **elige un vencimiento con DTE > 0** (¡ojo con 0DTE, que da todo "Evitar"!).
- [ ] Aparecen las tarjetas **RECOMENDADO** (verde) y **AGRESIVO** (amarillo) con score, strike, prima, Δ, spread, break-even.
- [ ] El Δ del recomendado cae en la zona sana (~0.35–0.60) y el spread no es disparatado.
- [ ] Si hay earnings antes del vencimiento, sale el **aviso ámbar**.

### Ranking de oportunidades
- [ ] El panel **🏆 Ranking** ya NO muestra todo en "Esperar": al menos una fila accionable con medalla 🥇 **Mejor** / 🥈 **Segunda**.
- [ ] La fila accionable trae **plan** (Entrada/Stop/T1/T2/RR) y **contrato** 🎟️.
- [ ] El resumen de arriba muestra el régimen y "X accionables de Y".
- [ ] Clic en un ticker del ranking → lo carga y lo analiza abajo.

### Módulo de salida (seguimiento de posición)
- [ ] En el diario, registra una posición **CALL o PUT** con su **contrato** (strike, vencimiento, prima pagada). Usa el autocompletado del recomendado y ajusta la **prima a lo que "pagaste"**.
- [ ] La posición aparece en el panel **Salida** con: PRIMA entrada → actual, **P/L sobre la prima** (%), subyacente, stop, Θ/IV.
- [ ] Observa un rato cómo se mueve el **P/L de la prima** al refrescar (🔄) según se mueve el contrato.
- [ ] Comprueba la **señal de salida** según el caso: MANTENER / +15 / +20 / +30% / DEFENSIVA (−25%) / SALIR (tesis rota) / VIGILA TIEMPO.

---

## 3) Todo el día (en segundo plano)

### Alertas a Telegram (monitor)
- [ ] Deja el Monitor corriendo. Cuando un ticker de la watchlist **cambie de señal** (NO OPERAR → CALL/PUT, o CALL ↔ PUT), debe llegar la **alerta directa CALL/PUT**: dirección + entrada/stop/objetivos + R:R + contrato sugerido (sin spam, con cooldown).
- [ ] La alerta es **100% determinista** (sale del motor `decision_signal`, sin IA ni coste de OpenAI). Verifica que el plan de la alerta coincide con el que ves en la web (panel Señal).
- [ ] **Alerta de cruce de nivel**: cuando el precio cruce un R/S de la escalera, debe llegar el aviso corto (🚀 rompió / 🔻 perdió). Primera lectura solo fija referencia (no alerta).

### Watchlist en vivo
- [ ] Los **chips de la watchlist** muestran punto de color (clasificación), flecha de tendencia y % desde apertura, y se actualizan con 🔄 Estado.

---

## 4) Cierre — cerca de las 16:00 ET (diario y estadísticas)

- [ ] Para las posiciones/decisiones del día, marca su **resultado** (acierto / fallo / neutra) en el diario.
- [ ] El panel **📊 Estadísticas del diario** se actualiza solo: **win-rate**, racha (🔥/❄️), y desgloses **por ticker** y **por hora** se rellenan con lo de hoy.
- [ ] Comprueba que la **hora** de cada decisión cae en el bucket correcto (la columna "Por hora del día" usa hora ET).
- [ ] Tras las 16:00, el banner de régimen vuelve a ⚪ **NO OPERAR · "Mercado cerrado"**.

---

## 5) Hallazgos (apunta aquí lo que falle o sorprenda)

> Formato sugerido: **[Módulo] — qué pasó — qué esperabas — ticker/hora**.

- 
- 
- 

---

## Notas rápidas de operación
- Si un panel se queda colgado, primero pulsa su botón **🔄**; si sigue, recarga la página (F5).
- Si el backend se cae: en su ventana, `Ctrl+C` y relanza, o cierra y vuelve a `iniciar.bat`.
- Conversión de horas: 9:30 ET = 15:30 en España peninsular (verano). Ajusta a tu huso.
- Vigila el **espacio en disco C:** (hubo un incidente de disco lleno); si baja de ~2 GB, libera antes de seguir.
