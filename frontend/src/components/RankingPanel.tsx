import { useCallback, useEffect, useState } from "react"
import {
  fetchRanking,
  type OpportunityRow,
  type RankingResult,
} from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

// Estilo del badge de señal (CALL verde / PUT rojo / NO OPERAR neutro).
function signalBadge(signal: string | null): string {
  if (signal === "CALL") return "bg-green-600 text-white"
  if (signal === "PUT") return "bg-red-600 text-white"
  return "bg-muted text-muted-foreground"
}

// Estilo de la categoría (Mejor con medalla, Segunda, Esperar, Error).
function categoryChip(cat?: string): { label: string; cls: string } {
  switch (cat) {
    case "Mejor":
      return { label: "🥇 Mejor", cls: "bg-yellow-500 text-black" }
    case "Segunda":
      return { label: "🥈 Segunda", cls: "bg-blue-600/80 text-white" }
    case "Error":
      return { label: "Error", cls: "bg-red-600/70 text-white" }
    default:
      return { label: "Esperar", cls: "bg-muted text-muted-foreground" }
  }
}

function confColor(c?: number): string {
  if (c == null) return "text-muted-foreground"
  if (c >= 70) return "text-green-500"
  if (c >= 50) return "text-yellow-500"
  return "text-muted-foreground"
}

function rowRing(row: OpportunityRow): string {
  if (row.error) return "border-red-600/40 bg-red-600/5"
  if (row.signal === "CALL") return "border-green-600/40 bg-green-600/5"
  if (row.signal === "PUT") return "border-red-600/40 bg-red-600/5"
  return "border-border bg-muted/15"
}

function OpportunityCard({
  row,
  onSelect,
}: {
  row: OpportunityRow
  onSelect?: (ticker: string) => void
}) {
  const chip = categoryChip(row.category)

  if (row.error) {
    return (
      <div className={`rounded-lg border px-4 py-3 ${rowRing(row)}`}>
        <div className="flex items-center justify-between">
          <span className="font-bold">{row.ticker}</span>
          <span className={`rounded px-2 py-0.5 text-xs font-semibold ${chip.cls}`}>
            {chip.label}
          </span>
        </div>
        <p className="mt-1 text-xs text-red-400">⚠️ {row.error}</p>
      </div>
    )
  }

  const actionable = row.signal === "CALL" || row.signal === "PUT"

  return (
    <div className={`rounded-lg border px-4 py-3 ${rowRing(row)}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onSelect?.(row.ticker)}
            className="font-bold underline-offset-2 hover:underline"
            title="Analizar este ticker"
          >
            {row.ticker}
          </button>
          {row.price != null && (
            <span className="text-sm text-muted-foreground">${row.price}</span>
          )}
          <span
            className={`rounded px-2 py-0.5 text-xs font-bold ${signalBadge(
              row.signal,
            )}`}
          >
            {row.signal}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {actionable && (
            <span className="text-xs text-muted-foreground">
              conf{" "}
              <span className={`font-bold ${confColor(row.confidence)}`}>
                {row.confidence}%
              </span>
            </span>
          )}
          <span className={`rounded px-2 py-0.5 text-xs font-semibold ${chip.cls}`}>
            {chip.label}
          </span>
        </div>
      </div>

      {/* Razón / veto */}
      <p className="mt-1 text-xs text-muted-foreground">
        {row.signal === "NO OPERAR"
          ? row.veto_reason ?? row.reason
          : row.reason}
      </p>

      {/* Plan operativo (solo accionables) */}
      {actionable && row.plan && (
        <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-5">
          <Mini label="Entrada" value={`$${row.plan.entry}`} accent="text-blue-400" />
          <Mini label="Stop" value={`$${row.plan.stop}`} accent="text-red-400" />
          <Mini label="T1" value={`$${row.plan.target1}`} accent="text-green-400" />
          <Mini label="T2" value={`$${row.plan.target2}`} accent="text-green-400" />
          <Mini
            label="R:R"
            value={`${row.plan.rr}`}
            accent={row.plan.rr >= 1.5 ? "text-green-500" : "text-yellow-500"}
          />
        </div>
      )}

      {/* Contrato sugerido (solo accionables) */}
      {actionable && row.contract && (
        <div className="mt-2 rounded-md border border-border bg-background/40 px-3 py-2 text-xs">
          🎟️{" "}
          <span className="font-semibold uppercase">{row.contract.type}</span>{" "}
          ${row.contract.strike} · Δ {row.contract.delta} · mid $
          {row.contract.mid} · score {row.contract.score}
          {row.contract.earnings_warning && (
            <span className="ml-2 text-yellow-500">⚠️ earnings cerca</span>
          )}
        </div>
      )}
    </div>
  )
}

function Mini({
  label,
  value,
  accent,
}: {
  label: string
  value: string
  accent?: string
}) {
  return (
    <div className="rounded border border-border/60 bg-background/30 px-2 py-1">
      <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
      <div className={`text-sm font-semibold tabular-nums ${accent ?? ""}`}>
        {value}
      </div>
    </div>
  )
}

export function RankingPanel({
  onSelect,
}: {
  onSelect?: (ticker: string) => void
}) {
  const [data, setData] = useState<RankingResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchRanking()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false))
  }, [])

  // Carga automática al montar (el usuario eligió "automático al abrir").
  useEffect(() => {
    load()
  }, [load])

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
        <CardTitle className="text-sm text-muted-foreground">
          🏆 Ranking de oportunidades · ¿dónde hay ventaja hoy? (gratis)
        </CardTitle>
        <Button
          variant="outline"
          size="sm"
          onClick={load}
          disabled={loading}
          className="h-7 text-xs"
        >
          {loading ? "Calculando…" : "🔄 Refrescar"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading && !data && (
          <p className="text-sm text-muted-foreground">
            Calculando ranking de la watchlist… puede tardar unos segundos.
          </p>
        )}
        {error && <p className="text-sm text-red-500">⚠️ {error}</p>}

        {data && (
          <>
            {/* Resumen: régimen + conteo */}
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>
                Régimen:{" "}
                <span className="font-semibold">
                  {data.regime.regime ?? "—"}
                </span>
                {data.regime.score != null && ` (${data.regime.score})`}
                {data.regime.veto_reason && ` · ${data.regime.veto_reason}`}
              </span>
              <span>
                {data.count_actionable} accionable
                {data.count_actionable === 1 ? "" : "s"} de {data.count_total}
              </span>
            </div>

            {data.ranked.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Watchlist vacía. Añade tickers para ver el ranking.
              </p>
            ) : (
              <div className="space-y-2">
                {data.ranked.map((row) => (
                  <OpportunityCard
                    key={row.ticker}
                    row={row}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              Determinista (sin IA, gratis). Régimen calculado una vez y reusado.
              Solo prioriza el foco; no ejecuta órdenes.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
