import { useEffect, useState } from "react"
import {
  fetchOptions,
  fetchContracts,
  type OptionChain,
  type ContractRecommendation,
  type ScoredContract,
} from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

function fmtExpiry(d: string): string {
  const [y, m, day] = d.split("-")
  const meses = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
  ]
  return `${Number(day)} ${meses[Number(m) - 1]} ${y}`
}

// --------------------------------------------------------------------------- //
//  Contrato recomendado (Paso 4): el scorer elige; aquí lo presentamos.
// --------------------------------------------------------------------------- //
function dirBadgeClass(dir: string): string {
  if (dir === "CALL") return "bg-green-600 text-white"
  if (dir === "PUT") return "bg-red-600 text-white"
  return "bg-muted text-muted-foreground"
}

function scoreClass(s: number): string {
  if (s >= 80) return "text-green-500"
  if (s >= 60) return "text-yellow-500"
  return "text-muted-foreground"
}

// Ratio break-even / movimiento esperado: <0.75 favorable, <=1 al borde, >1 caro.
function emRatioClass(r: number | null): string {
  if (r == null) return "text-muted-foreground"
  if (r <= 0.75) return "text-green-500"
  if (r <= 1.0) return "text-yellow-500"
  return "text-red-500"
}

function emRatioLabel(r: number | null): string {
  if (r == null) return "—"
  return `${r}x`
}

// Tarjeta de un contrato elegido (Recomendado / Agresivo).
function PickCard({
  pick,
  tone,
}: {
  pick: ScoredContract
  tone: "rec" | "agg"
}) {
  const ring =
    tone === "rec"
      ? "border-green-600/50 bg-green-600/5"
      : "border-yellow-500/50 bg-yellow-500/5"
  const label = tone === "rec" ? "✅ Recomendado" : "⚡ Agresivo"
  const labelColor = tone === "rec" ? "text-green-500" : "text-yellow-500"
  return (
    <div className={`min-w-0 rounded-lg border px-4 py-3 ${ring}`}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className={`text-xs font-semibold uppercase tracking-wide ${labelColor}`}>
          {label}
        </span>
        <span className={`text-2xl font-bold tabular-nums ${scoreClass(pick.score)}`}>
          {pick.score}
        </span>
      </div>
      <div className="mb-2 text-lg font-bold">
        {pick.type.toUpperCase()} ${pick.strike}{" "}
        <span className="text-sm font-normal text-muted-foreground">
          · prima ${pick.mid}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
        <Spec label="Δ delta" value={`${pick.delta}`} />
        <Spec
          label="Spread"
          value={`${pick.spread_pct}%`}
          accent={pick.spread_pct > 10 ? "text-red-500" : undefined}
        />
        <Spec
          label="Mov. BE"
          value={`${pick.break_even_move_pct >= 0 ? "+" : ""}${pick.break_even_move_pct}%`}
        />
        <Spec
          label="BE / esperado"
          value={emRatioLabel(pick.be_em_ratio)}
          accent={emRatioClass(pick.be_em_ratio)}
        />
        <Spec label="Break-even" value={`$${pick.break_even}`} />
        <Spec label="OI / Vol" value={`${pick.open_interest}/${pick.volume}`} />
        <Spec label="IV / Θ" value={`${pick.iv}% · ${pick.theta}`} />
      </div>
      {pick.reasons.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {pick.reasons.map((r, i) => (
            <span
              key={i}
              className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              {r}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function Spec({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent?: string
}) {
  return (
    <div>
      <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
      <div className={`font-semibold tabular-nums ${accent ?? ""}`}>{value}</div>
    </div>
  )
}

function RecommendationBlock({ rec }: { rec: ContractRecommendation }) {
  const hasPick = rec.recommended != null
  return (
    <div className="mb-5 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold">🎯 Contrato recomendado</span>
        <span
          className={`rounded-md px-2 py-0.5 text-xs font-bold ${dirBadgeClass(rec.direction)}`}
        >
          {rec.direction}
        </span>
        {rec.signal_state && (
          <span className="text-xs text-muted-foreground">
            · señal {rec.signal_state}
          </span>
        )}
        {rec.dte != null && (
          <span className="text-xs text-muted-foreground">
            · {rec.dte}d al venc.
          </span>
        )}
        {rec.expected_move_pct != null && (
          <span
            className="text-xs text-muted-foreground"
            title={`Movimiento esperado del vencimiento (${
              rec.em_method === "straddle" ? "straddle ATM" : "fórmula IV"
            }). Un contrato es eficiente si su movimiento al break-even cae DENTRO de este rango.`}
          >
            · 🎯 mov. esperado ±{rec.expected_move_pct}%
            {rec.expected_move != null && ` ($${rec.expected_move})`}
          </span>
        )}
      </div>

      {rec.earnings_warning && (
        <div className="rounded-md border border-yellow-500/50 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-600 dark:text-yellow-400">
          ⚠️ Earnings {rec.earnings_date} antes del vencimiento — la IV puede
          colapsar tras el reporte (penalizado en el score).
        </div>
      )}

      {hasPick ? (
        <div className="grid gap-3 md:grid-cols-2">
          <PickCard pick={rec.recommended!} tone="rec" />
          {rec.aggressive ? (
            <PickCard pick={rec.aggressive} tone="agg" />
          ) : (
            <div className="flex min-w-0 items-center justify-center rounded-lg border border-dashed border-border px-4 py-3 text-xs text-muted-foreground">
              Sin alternativa agresiva viable (las más OTM están descalificadas).
            </div>
          )}
        </div>
      ) : (
        <div className="rounded-md border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
          {rec.note}
        </div>
      )}

      {hasPick && (
        <p className="text-xs text-muted-foreground">
          {rec.note} El scorer pondera delta, spread, liquidez, IV y el{" "}
          <strong>break-even frente al movimiento esperado</strong> (🟢 &lt;0.75x
          dentro · 🟡 ≤1x al borde · 🔴 &gt;1x pide más de lo que el mercado espera).{" "}
          {rec.avoid.length > 0 && `${rec.avoid.length} descartados por spread/liquidez/lotería.`}{" "}
          Solo análisis, no ejecuta órdenes.
        </p>
      )}
    </div>
  )
}

export function OptionsPanel({ ticker }: { ticker: string }) {
  const [chain, setChain] = useState<OptionChain | null>(null)
  const [expiry, setExpiry] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rec, setRec] = useState<ContractRecommendation | null>(null)

  // Al cambiar de ticker, reseteamos el vencimiento elegido.
  useEffect(() => {
    setExpiry(undefined)
  }, [ticker])

  useEffect(() => {
    let cancel = false
    setLoading(true)
    setError(null)
    fetchOptions(ticker, expiry)
      .then((c) => {
        if (!cancel) setChain(c)
      })
      .catch((e) => {
        if (!cancel) {
          setError(e instanceof Error ? e.message : "Error")
          setChain(null)
        }
      })
      .finally(() => {
        if (!cancel) setLoading(false)
      })
    return () => {
      cancel = true
    }
  }, [ticker, expiry])

  // Contrato recomendado: dirección la deriva el backend de la señal (Paso 3).
  // Mismo vencimiento que la cadena para que no se descoordinen. No bloquea la UI.
  useEffect(() => {
    let cancel = false
    setRec(null)
    fetchContracts(ticker, undefined, expiry)
      .then((r) => {
        if (!cancel) setRec(r)
      })
      .catch(() => {
        if (!cancel) setRec(null)
      })
    return () => {
      cancel = true
    }
  }, [ticker, expiry])

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 pb-2">
        <CardTitle className="text-sm text-muted-foreground">
          🎟️ Contrato recomendado · cerca del dinero
          {chain && (
            <span className="ml-2 font-normal">
              · Subyacente ${chain.underlying_price.toFixed(2)}
              {chain.dte != null && ` · ${chain.dte}d al vencimiento`}
            </span>
          )}
        </CardTitle>
        {chain && (
          <select
            value={chain.expiry}
            onChange={(e) => setExpiry(e.target.value)}
            className="rounded-md border border-border bg-background px-2 py-1 text-xs"
          >
            {chain.available_expiries.map((d) => (
              <option key={d} value={d}>
                {fmtExpiry(d)}
              </option>
            ))}
          </select>
        )}
      </CardHeader>
      <CardContent>
        {loading && (
          <p className="text-sm text-muted-foreground">Cargando opciones...</p>
        )}
        {error && <p className="text-sm text-red-500">⚠️ {error}</p>}

        {chain && !loading && !error && (
          <>
            {rec ? (
              <RecommendationBlock rec={rec} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Sin contrato recomendado para este vencimiento.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
