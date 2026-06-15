import { useCallback, useEffect, useState } from "react"
import { fetchPositions, type Position } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

function toneClasses(tone?: string): { ring: string; badge: string } {
  switch (tone) {
    case "verde":
      return { ring: "border-green-600/50 bg-green-600/5", badge: "bg-green-600 text-white" }
    case "rojo":
      return { ring: "border-red-600/50 bg-red-600/5", badge: "bg-red-600 text-white" }
    case "amarillo":
      return {
        ring: "border-yellow-500/50 bg-yellow-500/5",
        badge: "bg-yellow-500 text-black",
      }
    default:
      return { ring: "border-border bg-muted/20", badge: "bg-muted text-muted-foreground" }
  }
}

function pnlClass(pct?: number): string {
  if (pct == null) return ""
  if (pct > 0) return "text-green-500"
  if (pct < 0) return "text-red-500"
  return ""
}

function fmtExpiryShort(d: string): string {
  const parts = d.split("-")
  if (parts.length !== 3) return d
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
  return `${Number(parts[2])} ${meses[Number(parts[1]) - 1]}`
}

function PositionCard({ p }: { p: Position }) {
  const t = toneClasses(p.tone)

  if (p.error) {
    return (
      <div className="rounded-lg border border-border bg-muted/20 px-4 py-3 text-sm">
        <span className="font-semibold">
          {p.decision} {p.ticker} ${p.strike}
        </span>{" "}
        <span className="text-muted-foreground">· {fmtExpiryShort(p.expiry)}</span>
        <p className="mt-1 text-xs text-yellow-500">⚠️ {p.error}</p>
      </div>
    )
  }

  return (
    <div className={`rounded-lg border px-4 py-3 ${t.ring}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={`rounded-md px-2 py-0.5 text-xs font-bold ${
              p.decision === "CALL" ? "bg-green-600 text-white" : "bg-red-600 text-white"
            }`}
          >
            {p.decision}
          </span>
          <span className="font-semibold">
            {p.ticker} ${p.strike}
          </span>
          <span className="text-xs text-muted-foreground">
            · {fmtExpiryShort(p.expiry)}
            {p.dte != null && ` · ${p.dte}d`}
          </span>
        </div>
        <span className={`rounded-md px-2 py-0.5 text-xs font-bold ${t.badge}`}>
          {p.signal_label ?? p.signal}
        </span>
      </div>

      {/* P/L sobre la prima */}
      <div className="mt-2 flex flex-wrap items-end gap-x-5 gap-y-1 text-sm">
        <div>
          <div className="text-[10px] uppercase text-muted-foreground">Prima</div>
          <div className="tabular-nums">
            ${p.entry_premium} → <strong>${p.current_premium}</strong>
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase text-muted-foreground">P/L prima</div>
          <div className={`text-lg font-bold tabular-nums ${pnlClass(p.pnl_pct)}`}>
            {p.pnl_pct != null && p.pnl_pct >= 0 ? "+" : ""}
            {p.pnl_pct}%
          </div>
        </div>
        <div>
          <div className="text-[10px] uppercase text-muted-foreground">Subyacente</div>
          <div className="tabular-nums">
            ${p.underlying_price}
            {p.stop != null && (
              <span className="text-xs text-muted-foreground"> · stop ${p.stop}</span>
            )}
          </div>
        </div>
        {p.theta != null && (
          <div>
            <div className="text-[10px] uppercase text-muted-foreground">Θ/día · IV</div>
            <div className="tabular-nums text-muted-foreground">
              {p.theta} · {p.iv}%
            </div>
          </div>
        )}
      </div>

      {p.action && <p className="mt-2 text-sm">{p.action}</p>}
      {p.note && (
        <p className="mt-1 text-xs italic text-muted-foreground">Tesis: {p.note}</p>
      )}
    </div>
  )
}

export function ExitPanel({ refreshKey = 0 }: { refreshKey?: number }) {
  const [positions, setPositions] = useState<Position[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchPositions()
      .then(setPositions)
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false))
  }, [])

  // Recarga al montar y cada vez que cambia refreshKey (p.ej. tras registrar).
  useEffect(() => {
    load()
  }, [load, refreshKey])

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 pb-2">
        <CardTitle className="text-sm text-muted-foreground">
          🚪 Salida · posiciones abiertas (+15/+20/+30%, defensa, tesis)
        </CardTitle>
        <button
          onClick={load}
          disabled={loading}
          className="text-xs text-muted-foreground hover:text-foreground"
          title="Recargar primas en vivo"
        >
          {loading ? "Actualizando…" : "🔄 Refrescar"}
        </button>
      </CardHeader>
      <CardContent className="space-y-3">
        {error && <p className="text-sm text-red-500">⚠️ {error}</p>}

        {!loading && !error && positions.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No hay posiciones abiertas con contrato. Registra un CALL/PUT con su prima
            en el diario para seguir la salida aquí.
          </p>
        )}

        {positions.map((p) => (
          <PositionCard key={p.id} p={p} />
        ))}

        {positions.length > 0 && (
          <p className="text-xs text-muted-foreground">
            P/L calculado sobre la PRIMA (prima actual vs prima de entrada), no sobre la
            acción. Solo avisa; tú decides y ejecutas en tu broker.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
