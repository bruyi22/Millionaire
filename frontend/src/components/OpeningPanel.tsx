import { useEffect, useState } from "react"
import { fetchOpening, type OpeningAnalysis } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

// Color de la señal de apertura.
function signalStyle(signal: string): { badge: string; text: string } {
  switch (signal) {
    case "CALL":
      return { badge: "bg-green-600 text-white", text: "text-green-400" }
    case "PUT":
      return { badge: "bg-red-600 text-white", text: "text-red-400" }
    case "NO OPERAR":
      return { badge: "bg-muted text-muted-foreground", text: "text-muted-foreground" }
    case "ESPERAR":
      return { badge: "bg-yellow-500 text-black", text: "text-yellow-400" }
    default: // OBSERVAR
      return { badge: "bg-blue-600 text-white", text: "text-blue-400" }
  }
}

function confidenceStyle(c: string): string {
  if (c === "alta") return "text-green-500"
  if (c === "media") return "text-yellow-500"
  return "text-muted-foreground"
}

// Marca un evento del relato con color según su carácter.
function eventTone(ev: string): string {
  const e = ev.toLowerCase()
  if (e.includes("con volumen") && e.includes("máximo")) return "text-green-400"
  if (e.includes("con volumen") && e.includes("mínimo")) return "text-red-400"
  if (e.includes("alcista") || e.includes("recuperación")) return "text-green-400"
  if (e.includes("bajista") || e.includes("pérdida") || e.includes("shakeout"))
    return "text-red-400"
  if (e.includes("falsa") || e.includes("flojo")) return "text-yellow-400"
  return "text-muted-foreground"
}

export function OpeningPanel({ ticker }: { ticker: string }) {
  const [data, setData] = useState<OpeningAnalysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchOpening(ticker)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Error"))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [ticker])

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 pb-2">
        <CardTitle className="text-sm text-muted-foreground">
          🔔 Apertura 9:30–10:00 ET · disciplina de la primera media hora
        </CardTitle>
        {data && (
          <span className="text-xs text-muted-foreground">
            {data.live ? "🟢 en vivo" : "última sesión"} · {data.session_date}
          </span>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && (
          <p className="text-sm text-muted-foreground">Leyendo la apertura…</p>
        )}
        {error && <p className="text-sm text-red-500">⚠️ {error}</p>}

        {data && !loading && (
          <>
            {/* Señal + fase */}
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`rounded-md px-3 py-1 text-sm font-bold ${
                  signalStyle(data.signal).badge
                }`}
              >
                {data.signal}
              </span>
              <span className="text-sm text-muted-foreground">
                Fase: <span className="font-medium">{data.phase_label}</span>
              </span>
              <span className="text-sm text-muted-foreground">
                Confianza:{" "}
                <span className={`font-medium ${confidenceStyle(data.confidence)}`}>
                  {data.confidence}
                </span>
              </span>
            </div>

            {/* Nota directa */}
            <p className={`text-sm ${signalStyle(data.signal).text}`}>{data.note}</p>

            {/* Métricas clave */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric
                label="Rango apertura"
                value={`${data.opening_range.low} – ${data.opening_range.high}`}
              />
              <Metric
                label="VWAP"
                value={`$${data.vwap}`}
                hint={data.above_vwap ? "precio sobre VWAP" : "precio bajo VWAP"}
                hintClass={data.above_vwap ? "text-green-500" : "text-red-500"}
              />
              <Metric
                label="Hueco"
                value={`${data.gap_pct >= 0 ? "+" : ""}${data.gap_pct}%`}
                hint={`premarket ${data.premarket_bias}`}
                valueClass={
                  data.gap_pct > 0
                    ? "text-green-500"
                    : data.gap_pct < 0
                      ? "text-red-500"
                      : ""
                }
              />
              <Metric label="Precio" value={`$${data.current_price}`} />
            </div>

            {/* Relato del día como timeline */}
            <div>
              <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                Relato del día
              </p>
              <div className="flex flex-wrap items-center gap-1.5 text-sm">
                {data.events.map((ev, i) => (
                  <span key={i} className="flex items-center gap-1.5">
                    <span className={eventTone(ev)}>{ev}</span>
                    {i < data.events.length - 1 && (
                      <span className="text-muted-foreground">→</span>
                    )}
                  </span>
                ))}
                <span className="text-muted-foreground">→</span>
                <span className={`font-semibold ${signalStyle(data.signal).text}`}>
                  {data.signal}
                </span>
              </div>
            </div>

            <p className="text-xs text-muted-foreground">
              Solo análisis, no ejecuta órdenes. Antes de 9:45 el módulo solo observa.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}

function Metric({
  label,
  value,
  hint,
  valueClass,
  hintClass,
}: {
  label: string
  value: string
  hint?: string
  valueClass?: string
  hintClass?: string
}) {
  return (
    <div className="rounded-md border border-border bg-muted/30 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-base font-semibold tabular-nums ${valueClass ?? ""}`}>
        {value}
      </div>
      {hint && <div className={`text-xs ${hintClass ?? "text-muted-foreground"}`}>{hint}</div>}
    </div>
  )
}
