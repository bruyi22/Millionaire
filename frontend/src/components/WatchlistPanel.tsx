import { useCallback, useEffect, useState } from "react"
import {
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  fetchWatchlistStatus,
  type WatchlistStatus,
} from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

// Punto de color segun la clasificacion del Risk Manager.
function dotColor(classification: string | null): string {
  if (classification === "Alta") return "bg-green-500"
  if (classification === "Riesgosa") return "bg-red-500"
  if (classification === "Media") return "bg-yellow-500"
  return "bg-muted-foreground" // sin datos / cargando
}

function trendArrow(trend: string | null): string {
  if (trend === "Alcista") return "↑"
  if (trend === "Bajista") return "↓"
  if (trend === "Lateral") return "→"
  return ""
}

export function WatchlistPanel({
  active,
  onSelect,
}: {
  active?: string
  onSelect: (ticker: string) => void
}) {
  const [tickers, setTickers] = useState<string[]>([])
  const [status, setStatus] = useState<Record<string, WatchlistStatus>>({})
  const [loadingStatus, setLoadingStatus] = useState(false)
  const [nuevo, setNuevo] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Carga el estado (clasificacion/tendencia/%) de todos en segundo plano.
  const loadStatus = useCallback(async () => {
    setLoadingStatus(true)
    try {
      const list = await fetchWatchlistStatus()
      const map: Record<string, WatchlistStatus> = {}
      for (const s of list) map[s.ticker] = s
      setStatus(map)
    } catch {
      // El estado es un extra; si falla, los chips siguen funcionando.
    } finally {
      setLoadingStatus(false)
    }
  }, [])

  useEffect(() => {
    getWatchlist()
      .then((ts) => {
        setTickers(ts)
        loadStatus()
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
  }, [loadStatus])

  async function agregar() {
    const t = nuevo.trim().toUpperCase()
    if (!t) return
    setBusy(true)
    setError(null)
    try {
      setTickers(await addToWatchlist(t))
      setNuevo("")
      loadStatus()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al agregar")
    } finally {
      setBusy(false)
    }
  }

  async function quitar(t: string) {
    setBusy(true)
    setError(null)
    try {
      setTickers(await removeFromWatchlist(t))
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al quitar")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 pb-2">
        <CardTitle className="text-sm text-muted-foreground">
          👁️ Watchlist · el monitor vigila estos tickers
        </CardTitle>
        <button
          type="button"
          onClick={loadStatus}
          disabled={loadingStatus}
          className="text-xs text-muted-foreground hover:text-foreground"
          title="Actualizar el estado de todos"
        >
          {loadingStatus ? "Actualizando…" : "🔄 Estado"}
        </button>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Input
            value={nuevo}
            onChange={(e) => setNuevo(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && agregar()}
            placeholder="Añadir ticker"
            className="max-w-[160px]"
          />
          <Button size="sm" variant="secondary" onClick={agregar} disabled={busy}>
            Añadir
          </Button>
        </div>

        {error && <p className="text-sm text-red-500">⚠️ {error}</p>}

        <div className="flex flex-wrap gap-2">
          {tickers.length === 0 && (
            <p className="text-sm text-muted-foreground">Watchlist vacía.</p>
          )}
          {tickers.map((t) => {
            const s = status[t]
            const change = s?.distance_from_open_pct
            return (
              <span
                key={t}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm ${
                  t === active
                    ? "border-blue-500 bg-blue-500/15 text-blue-300"
                    : "border-border bg-muted/40"
                }`}
                title={
                  s?.error
                    ? `Error: ${s.error}`
                    : s
                      ? `${s.classification} · ${s.trend} · $${s.price}`
                      : "Cargando estado…"
                }
              >
                <span
                  className={`inline-block h-2 w-2 rounded-full ${dotColor(
                    s?.classification ?? null,
                  )}`}
                />
                <button
                  type="button"
                  onClick={() => onSelect(t)}
                  className="font-medium hover:underline"
                >
                  {t}
                </button>
                {s && !s.error && (
                  <span className="text-xs text-muted-foreground">
                    {trendArrow(s.trend)}
                  </span>
                )}
                {change != null && (
                  <span
                    className={`text-xs tabular-nums ${
                      change >= 0 ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    {change >= 0 ? "+" : ""}
                    {change}%
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => quitar(t)}
                  disabled={busy}
                  aria-label={`Quitar ${t}`}
                  className="ml-0.5 text-muted-foreground hover:text-red-500"
                >
                  ✕
                </button>
              </span>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
