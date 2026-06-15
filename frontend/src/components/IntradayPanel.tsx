import { useCallback, useEffect, useRef, useState } from "react"
import {
  fetchIntraday,
  type IntradayData,
  type QuickTriggers,
  type Trigger,
} from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { CandleChart } from "@/components/CandleChart"

const REFRESH_MS = 30000

function TriggerLine({
  kind,
  trig,
}: {
  kind: "call" | "put"
  trig: Trigger | null
}) {
  const isCall = kind === "call"
  if (!trig) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span>{isCall ? "📈" : "📉"}</span>
        <span>
          Sin nivel {isCall ? "por encima" : "por debajo"} (precio en extremo del
          rango).
        </span>
      </div>
    )
  }
  const verbo = isCall ? "rompe" : "pierde"
  const sign = trig.distance_pct >= 0 ? "+" : ""
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm">
      <span>{isCall ? "📈" : "📉"}</span>
      <span className={`font-semibold ${isCall ? "text-green-500" : "text-red-500"}`}>
        {isCall ? "CALL" : "PUT"}
      </span>
      <span className="text-muted-foreground">si {verbo}</span>
      <span className="font-medium">
        {trig.level} ${trig.price}
      </span>
      <span className="tabular-nums text-xs text-muted-foreground">
        ({sign}
        {trig.distance_pct}% desde aquí)
      </span>
    </div>
  )
}

function TriggersBand({ triggers }: { triggers: QuickTriggers }) {
  const biasStyle =
    triggers.bias === "CALL"
      ? "border-green-600/50 text-green-500"
      : triggers.bias === "PUT"
        ? "border-red-600/50 text-red-500"
        : "border-border text-muted-foreground"
  const biasLabel =
    triggers.bias === "CALL"
      ? "Sesgo alcista (sobre pivote)"
      : triggers.bias === "PUT"
        ? "Sesgo bajista (bajo pivote)"
        : "Neutral (en el pivote)"

  return (
    <div className="mb-3 rounded-lg border border-border bg-muted/30 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          🚦 Disparadores (niveles, sin IA)
        </p>
        <span
          className={`rounded-full border px-2 py-0.5 text-xs font-medium ${biasStyle}`}
        >
          {biasLabel}
        </span>
      </div>
      <div className="space-y-1.5">
        <TriggerLine kind="call" trig={triggers.call} />
        <TriggerLine kind="put" trig={triggers.put} />
      </div>
      {triggers.call && triggers.put && (
        <p className="mt-2 text-xs text-muted-foreground">
          ⏸️ Entre ${triggers.put.price} y ${triggers.call.price}: zona de no
          operar (esperar ruptura, no perseguir).
        </p>
      )}
    </div>
  )
}

const LEGEND: { key: keyof IntradayData["levels"]; label: string; color: string }[] = [
  { key: "r2", label: "R2", color: "#f87171" },
  { key: "r1", label: "R1", color: "#ef4444" },
  { key: "pivot", label: "Pivot", color: "#9ca3af" },
  { key: "s1", label: "S1", color: "#22c55e" },
  { key: "s2", label: "S2", color: "#4ade80" },
]

export function IntradayPanel({ ticker }: { ticker: string }) {
  const [data, setData] = useState<IntradayData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [auto, setAuto] = useState(true)
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const cancelRef = useRef(false)

  const load = useCallback(
    async (showSpinner: boolean) => {
      if (showSpinner) setLoading(true)
      try {
        const d = await fetchIntraday(ticker)
        if (!cancelRef.current) {
          setData(d)
          setUpdatedAt(new Date())
          setError(null)
        }
      } catch (e) {
        if (!cancelRef.current)
          setError(e instanceof Error ? e.message : "Error")
      } finally {
        if (!cancelRef.current && showSpinner) setLoading(false)
      }
    },
    [ticker],
  )

  useEffect(() => {
    cancelRef.current = false
    setData(null)
    load(true)
    return () => {
      cancelRef.current = true
    }
  }, [ticker, load])

  // Sondeo periodico (solo si auto esta activo y la pestana esta visible).
  useEffect(() => {
    if (!auto) return
    const id = setInterval(() => {
      if (!document.hidden) load(false)
    }, REFRESH_MS)
    return () => clearInterval(id)
  }, [auto, load])

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 pb-2">
        <CardTitle className="text-sm text-muted-foreground">
          🕯️ Velas 5m en vivo · niveles como disparadores
          {data && <span className="ml-2 font-normal">· ${data.current_price}</span>}
        </CardTitle>
        <div className="flex items-center gap-2 text-xs">
          {updatedAt && (
            <span className="text-muted-foreground">
              Actualizado {updatedAt.toLocaleTimeString("es", { hour12: false })}
            </span>
          )}
          <button
            type="button"
            onClick={() => setAuto((v) => !v)}
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 ${
              auto
                ? "border-green-600/50 text-green-500"
                : "border-border text-muted-foreground"
            }`}
            title={auto ? "Auto-refresco activo (30s)" : "Auto-refresco pausado"}
          >
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                auto ? "bg-green-500" : "bg-muted-foreground"
              }`}
            />
            {auto ? "Auto 30s" : "Pausado"}
          </button>
        </div>
      </CardHeader>
      <CardContent>
        {loading && !data && (
          <p className="text-sm text-muted-foreground">Cargando velas...</p>
        )}
        {error && !data && <p className="text-sm text-red-500">⚠️ {error}</p>}

        {data && (
          <>
            <TriggersBand triggers={data.triggers} />

            <CandleChart key={ticker} candles={data.candles} levels={data.levels} />

            {error && (
              <p className="mt-2 text-xs text-yellow-500">
                ⚠️ Último refresco falló ({error}); mostrando datos previos.
              </p>
            )}

            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {LEGEND.map((l) => (
                <span key={l.key} className="inline-flex items-center gap-1.5">
                  <span
                    className="inline-block h-2 w-3 rounded-sm"
                    style={{ backgroundColor: l.color }}
                  />
                  {l.label}{" "}
                  <span className="tabular-nums text-muted-foreground">
                    ${data.levels[l.key]}
                  </span>
                </span>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
