import { useEffect, useState } from "react"
import { fetchSignal, type DecisionSignal } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

function signalStyle(signal: string): { badge: string; ring: string; text: string } {
  switch (signal) {
    case "CALL":
      return {
        badge: "bg-green-600 text-white",
        ring: "border-green-600/50 bg-green-600/5",
        text: "text-green-400",
      }
    case "PUT":
      return {
        badge: "bg-red-600 text-white",
        ring: "border-red-600/50 bg-red-600/5",
        text: "text-red-400",
      }
    default: // NO OPERAR
      return {
        badge: "bg-muted text-muted-foreground",
        ring: "border-border bg-muted/20",
        text: "text-muted-foreground",
      }
  }
}

function confColor(c: number): string {
  if (c >= 70) return "text-green-500"
  if (c >= 50) return "text-yellow-500"
  return "text-muted-foreground"
}

// Traduce la señal + confianza en una INSTRUCCIÓN directa: "haz esto".
function directive(d: DecisionSignal): {
  headline: string
  action: string
  box: string
  head: string
} {
  if ((d.signal === "CALL" || d.signal === "PUT") && d.plan) {
    const c = d.confidence
    // Tres niveles de fuerza según confianza.
    let verbo: string
    let fuerza: string
    let size: string
    if (c >= 85) {
      verbo = "COMPRA FUERTE"
      fuerza = "señal muy fuerte"
      size = "Tamaño normal (puedes ir al máximo de tu plan)."
    } else if (c >= 80) {
      verbo = "COMPRA"
      fuerza = "confianza alta"
      size = "Tamaño normal."
    } else {
      verbo = "Considera comprar"
      fuerza = "confianza media"
      size = "Tamaño reducido (señal solo moderada)."
    }
    const icon = d.signal === "CALL" ? "🟢" : "🔴"
    const headline = `${icon} ${verbo} ${d.signal} · ${fuerza} (${c}%)`
    const action = `Entra cerca de $${d.plan.entry}, stop $${d.plan.stop}, objetivo $${d.plan.target1} (R:R ${d.plan.rr}). ${size} Arriesga máx. 1-2% de la cuenta.`
    const box =
      d.signal === "CALL"
        ? "border-green-600/50 bg-green-600/10"
        : "border-red-600/50 bg-red-600/10"
    const head = d.signal === "CALL" ? "text-green-400" : "text-red-400"
    return { headline, action, box, head }
  }
  // NO OPERAR
  return {
    headline: "🚫 NO OPERES ahora",
    action: `${d.veto_reason ?? d.reason} Quédate fuera y espera a que los factores se alineen con ventaja clara.`,
    box: "border-border bg-muted/30",
    head: "text-muted-foreground",
  }
}

function voteColor(vote: string): string {
  if (vote === "CALL") return "text-green-400"
  if (vote === "PUT") return "text-red-400"
  return "text-muted-foreground"
}

function proximityRing(state: string): string {
  switch (state) {
    case "pegado":
      return "border-green-600/40 bg-green-600/5 text-green-400"
    case "cerca":
      return "border-yellow-500/40 bg-yellow-500/5 text-yellow-400"
    case "lejos":
      return "border-orange-500/40 bg-orange-500/5 text-orange-400"
    default: // extendido (no debería verse: se veta antes)
      return "border-red-600/40 bg-red-600/5 text-red-400"
  }
}

function sessionChip(state: string): string {
  switch (state) {
    case "apertura":
    case "cierre":
      return "border-green-600/40 bg-green-600/10 text-green-400"
    case "media-manana":
    case "media-tarde":
      return "border-yellow-500/40 bg-yellow-500/10 text-yellow-400"
    case "mediodia":
      return "border-red-600/40 bg-red-600/10 text-red-400"
    default: // cerrado
      return "border-border bg-muted/30 text-muted-foreground"
  }
}

export function SignalPanel({ ticker }: { ticker: string }) {
  const [data, setData] = useState<DecisionSignal | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchSignal(ticker)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Error"))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [ticker])

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-muted-foreground">
          🎯 Señal estructurada · ¿hay ventaja o no? (gratis, determinista)
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && (
          <p className="text-sm text-muted-foreground">Calculando confluencias…</p>
        )}
        {error && <p className="text-sm text-red-500">⚠️ {error}</p>}

        {data && !loading && (
          <>
            {/* Veredicto */}
            <div
              className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 ${
                signalStyle(data.signal).ring
              }`}
            >
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-md px-3 py-1 text-base font-bold ${
                    signalStyle(data.signal).badge
                  }`}
                >
                  {data.signal}
                </span>
                <div className="text-sm">
                  <div>
                    Confianza{" "}
                    <span className={`font-bold ${confColor(data.confidence)}`}>
                      {data.confidence}%
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    acuerdo {Math.round(data.agreement * 100)}% · score{" "}
                    {data.net_score >= 0 ? "+" : ""}
                    {data.net_score}
                  </div>
                </div>
              </div>
              <div className="text-right text-sm text-muted-foreground">
                <div>
                  {data.ticker} · ${data.price}
                </div>
                <span
                  className={`mt-1 inline-block rounded-md border px-2 py-0.5 text-xs ${sessionChip(
                    data.session.session_state,
                  )}`}
                  title="Ventana horaria de la sesión (hora de Nueva York). Apertura y última hora concentran el edge; el mediodía suele ser chop con rupturas falsas. Ajusta la confianza, no veta."
                >
                  {data.session.session_label} · {data.session.et_time} ET
                </span>
              </div>
            </div>

            {/* Directiva directa: "haz esto" según señal + confianza */}
            {(() => {
              const dir = directive(data)
              return (
                <div className={`rounded-lg border px-4 py-3 ${dir.box}`}>
                  <p className={`text-base font-bold ${dir.head}`}>
                    {dir.headline}
                  </p>
                  <p className="mt-1 text-sm text-foreground/90">{dir.action}</p>
                </div>
              )
            })()}

            {/* Plan operativo (solo si hay señal) */}
            {data.plan && (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <Cell label="Setup" value={`$${data.plan.setup_level}`} />
                  <Cell label="Entrada" value={`$${data.plan.entry}`} accent="text-blue-400" />
                  <Cell label="Stop" value={`$${data.plan.stop}`} accent="text-red-400" />
                  <Cell label="Target 1" value={`$${data.plan.target1}`} accent="text-green-400" />
                  <Cell label="Target 2" value={`$${data.plan.target2}`} accent="text-green-400" />
                  <Cell
                    label="R:R"
                    value={`${data.plan.rr}`}
                    accent={data.plan.rr >= 1.5 ? "text-green-500" : "text-yellow-500"}
                  />
                </div>
                {/* Proximidad de la entrada al precio actual (en ATR) */}
                <div
                  className={`flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 text-xs ${proximityRing(
                    data.plan.proximity_state,
                  )}`}
                  title="Distancia del precio actual a la entrada, medida en múltiplos de ATR. Cuanto más lejos, más persigues un movimiento ya extendido."
                >
                  <span className="font-medium">{data.plan.proximity_label}</span>
                  <span className="text-muted-foreground">
                    entrada a {data.plan.entry_distance_atr} ATR ·{" "}
                    {data.plan.entry_distance_pct >= 0 ? "+" : ""}
                    {data.plan.entry_distance_pct}%
                  </span>
                </div>
              </>
            )}

            {/* Razón + contrato + riesgo (solo cuando hay operación) */}
            {data.plan && (
              <div className="space-y-1.5 text-sm">
                <p>
                  <span className="text-muted-foreground">Razón: </span>
                  {data.reason}
                </p>
                {data.contract_hint && (
                  <p>
                    <span className="text-muted-foreground">Contrato: </span>
                    {data.contract_hint}
                  </p>
                )}
                <p className={signalStyle(data.signal).text}>⚠️ {data.risk}</p>
              </div>
            )}

            {/* Tabla de factores que votaron */}
            <div>
              <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                Cómo votó cada factor
              </p>
              <table className="w-full text-sm">
                <tbody>
                  {data.factors.map((f) => (
                    <tr key={f.factor} className="border-t border-border/30">
                      <td className="py-1 font-medium">{f.factor}</td>
                      <td className="py-1 text-muted-foreground">{f.detail}</td>
                      <td className="py-1 text-right text-xs text-muted-foreground">
                        ×{f.weight}
                      </td>
                      <td
                        className={`py-1 pl-2 text-right font-semibold ${voteColor(f.vote)}`}
                      >
                        {f.vote}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-xs text-muted-foreground">
              Determinista (sin IA, gratis). Niveles desde pivots + ATR, no inventados.
              Solo análisis, no ejecuta órdenes.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}

function Cell({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent?: string
}) {
  return (
    <div className="rounded-md border border-border bg-muted/30 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`text-base font-semibold tabular-nums ${accent ?? ""}`}>
        {value}
      </div>
    </div>
  )
}
