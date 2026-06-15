import { useCallback, useEffect, useState } from "react"
import {
  fetchJournalStats,
  type JournalStats,
  type StatHourRow,
  type StatTickerRow,
} from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

// Color del win-rate: ≥60 verde, ≥40 amarillo, <40 rojo, sin datos gris.
function wrColor(wr: number | null): string {
  if (wr == null) return "text-muted-foreground"
  if (wr >= 60) return "text-green-500"
  if (wr >= 40) return "text-yellow-500"
  return "text-red-500"
}

function wrText(wr: number | null): string {
  return wr == null ? "—" : `${wr}%`
}

// Mini-barra horizontal de win-rate (gana verde / pierde rojo).
function WinBar({ wins, losses }: { wins: number; losses: number }) {
  const decided = wins + losses
  if (decided === 0) {
    return <div className="h-1.5 w-full rounded bg-muted" />
  }
  const winPct = (wins / decided) * 100
  return (
    <div className="flex h-1.5 w-full overflow-hidden rounded bg-muted">
      <div className="bg-green-500" style={{ width: `${winPct}%` }} />
      <div className="bg-red-500" style={{ width: `${100 - winPct}%` }} />
    </div>
  )
}

function Big({
  label,
  value,
  valueClass,
  hint,
}: {
  label: string
  value: string
  valueClass?: string
  hint?: string
}) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 px-3 py-2">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={`text-2xl font-bold tabular-nums ${valueClass ?? ""}`}>
        {value}
      </div>
      {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
    </div>
  )
}

function streakText(streak: JournalStats["streak"]): {
  text: string
  cls: string
} {
  if (!streak.type || streak.count === 0) {
    return { text: "—", cls: "text-muted-foreground" }
  }
  if (streak.type === "acierto") {
    return { text: `🔥 ${streak.count} acierto${streak.count === 1 ? "" : "s"}`, cls: "text-green-500" }
  }
  return { text: `❄️ ${streak.count} fallo${streak.count === 1 ? "" : "s"}`, cls: "text-red-500" }
}

function TickerRow({ r }: { r: StatTickerRow }) {
  return (
    <tr className="border-t border-border/30">
      <td className="py-1.5 font-medium">{r.ticker}</td>
      <td className="py-1.5 text-center text-muted-foreground">{r.total}</td>
      <td className="py-1.5 text-center text-green-500">{r.wins}</td>
      <td className="py-1.5 text-center text-red-500">{r.losses}</td>
      <td className={`py-1.5 text-right font-semibold ${wrColor(r.win_rate)}`}>
        {wrText(r.win_rate)}
      </td>
      <td className="w-24 py-1.5 pl-3 align-middle">
        <WinBar wins={r.wins} losses={r.losses} />
      </td>
    </tr>
  )
}

function HourRow({ r }: { r: StatHourRow }) {
  return (
    <tr className="border-t border-border/30">
      <td className="py-1.5 font-medium tabular-nums">{r.label}</td>
      <td className="py-1.5 text-center text-muted-foreground">{r.total}</td>
      <td className="py-1.5 text-center text-green-500">{r.wins}</td>
      <td className="py-1.5 text-center text-red-500">{r.losses}</td>
      <td className={`py-1.5 text-right font-semibold ${wrColor(r.win_rate)}`}>
        {wrText(r.win_rate)}
      </td>
      <td className="w-24 py-1.5 pl-3 align-middle">
        <WinBar wins={r.wins} losses={r.losses} />
      </td>
    </tr>
  )
}

export function JournalStatsPanel({ refreshKey = 0 }: { refreshKey?: number }) {
  const [data, setData] = useState<JournalStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchJournalStats()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  const streak = data ? streakText(data.streak) : null

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
        <CardTitle className="text-sm text-muted-foreground">
          📊 Estadísticas del diario · ¿qué te funciona? (gratis, por conteo)
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
      <CardContent className="space-y-4">
        {loading && !data && (
          <p className="text-sm text-muted-foreground">Leyendo el diario…</p>
        )}
        {error && <p className="text-sm text-red-500">⚠️ {error}</p>}

        {data && data.total === 0 && (
          <p className="text-sm text-muted-foreground">
            Aún no hay decisiones registradas. Cuando uses el diario y marques
            resultados (acierto/fallo), aquí verás tu win-rate y en qué tickers y
            horas te va mejor.
          </p>
        )}

        {data && data.total > 0 && (
          <>
            {/* Resumen general */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Big
                label="Win-rate"
                value={wrText(data.win_rate)}
                valueClass={wrColor(data.win_rate)}
                hint={`${data.wins}✓ / ${data.losses}✗ de ${data.closed} cerradas`}
              />
              <Big
                label="Racha actual"
                value={streak?.text ?? "—"}
                valueClass={streak?.cls}
              />
              <Big
                label="Registradas"
                value={`${data.total}`}
                hint={`${data.open} en curso · ${data.neutral} neutras`}
              />
              <Big
                label="Mejor / peor"
                value={`${data.best_win_streak} / ${data.worst_loss_streak}`}
                hint="racha de aciertos / fallos"
              />
            </div>

            {/* Por ticker */}
            {data.by_ticker.length > 0 && (
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                  Por ticker
                </p>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-muted-foreground">
                      <th className="py-1 text-left font-normal">Ticker</th>
                      <th className="py-1 text-center font-normal">Tot</th>
                      <th className="py-1 text-center font-normal">✓</th>
                      <th className="py-1 text-center font-normal">✗</th>
                      <th className="py-1 text-right font-normal">Win-rate</th>
                      <th className="py-1" />
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_ticker.map((r) => (
                      <TickerRow key={r.ticker} r={r} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Por hora del día */}
            {data.by_hour.length > 0 && (
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                  Por hora del día (ET)
                </p>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-muted-foreground">
                      <th className="py-1 text-left font-normal">Hora</th>
                      <th className="py-1 text-center font-normal">Tot</th>
                      <th className="py-1 text-center font-normal">✓</th>
                      <th className="py-1 text-center font-normal">✗</th>
                      <th className="py-1 text-right font-normal">Win-rate</th>
                      <th className="py-1" />
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_hour.map((r) => (
                      <HourRow key={r.hour} r={r} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              Win-rate sobre operaciones cerradas (acierto/fallo); las neutras y
              en curso no cuentan. Determinista, solo lectura — no ejecuta órdenes.
            </p>
          </>
        )}
      </CardContent>
    </Card>
  )
}
