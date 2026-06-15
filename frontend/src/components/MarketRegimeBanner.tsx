import { useCallback, useEffect, useState } from "react"
import { fetchMarketRegime, type MarketRegime } from "@/lib/api"

// Estilo del semaforo segun el regimen del mercado.
function regimeStyle(regime: string): {
  border: string
  bg: string
  text: string
  dot: string
  emoji: string
} {
  switch (regime) {
    case "ALCISTA":
      return {
        border: "border-green-600/50",
        bg: "bg-green-600/10",
        text: "text-green-400",
        dot: "bg-green-500",
        emoji: "🟢",
      }
    case "BAJISTA":
      return {
        border: "border-red-600/50",
        bg: "bg-red-600/10",
        text: "text-red-400",
        dot: "bg-red-500",
        emoji: "🔴",
      }
    case "MIXTO":
      return {
        border: "border-yellow-500/50",
        bg: "bg-yellow-500/10",
        text: "text-yellow-400",
        dot: "bg-yellow-500",
        emoji: "🟡",
      }
    default: // NO OPERAR
      return {
        border: "border-border",
        bg: "bg-muted/40",
        text: "text-muted-foreground",
        dot: "bg-muted-foreground",
        emoji: "⚪",
      }
  }
}

export function MarketRegimeBanner() {
  const [data, setData] = useState<MarketRegime | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await fetchMarketRegime())
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (error) {
    return (
      <div className="rounded-lg border border-red-600/50 bg-red-600/10 px-4 py-3 text-sm text-red-400">
        ⚠️ No se pudo leer el régimen de mercado: {error}{" "}
        <button onClick={load} className="underline hover:text-red-300">
          reintentar
        </button>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
        🧭 Leyendo el régimen de mercado…
      </div>
    )
  }

  const s = regimeStyle(data.regime)
  const scoreStr = `${data.score >= 0 ? "+" : ""}${data.score}`

  return (
    <div className={`rounded-lg border ${s.border} ${s.bg}`}>
      {/* Cabecera del semaforo */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3">
          <span className={`inline-block h-3 w-3 rounded-full ${s.dot}`} />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">
                Mercado
              </span>
              <span className={`text-lg font-bold ${s.text}`}>
                {s.emoji} {data.regime}
              </span>
              <span className={`text-sm font-semibold tabular-nums ${s.text}`}>
                {scoreStr}
              </span>
            </div>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {data.veto_reason ?? data.summary}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {data.vix_level != null && (
            <span title="Índice de volatilidad (miedo)">
              VIX {data.vix_level} {data.vix_label && `(${data.vix_label})`}
            </span>
          )}
          <button
            onClick={() => setOpen((v) => !v)}
            className="hover:text-foreground"
          >
            {open ? "Ocultar ▲" : "Desglose ▼"}
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="hover:text-foreground"
            title="Actualizar"
          >
            {loading ? "…" : "🔄"}
          </button>
        </div>
      </div>

      {/* Desglose plegable */}
      {open && (
        <div className="border-t border-border/50 px-4 py-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-muted-foreground">
                <th className="pb-1 text-left font-medium">Componente</th>
                <th className="pb-1 text-left font-medium">Detalle</th>
                <th className="pb-1 text-right font-medium">Peso</th>
                <th className="pb-1 text-right font-medium">Aporte</th>
              </tr>
            </thead>
            <tbody>
              {data.breakdown.map((c) => (
                <tr key={c.name} className="border-t border-border/30">
                  <td className="py-1 font-medium">{c.name}</td>
                  <td className="py-1 text-muted-foreground">{c.detail}</td>
                  <td className="py-1 text-right tabular-nums text-muted-foreground">
                    {c.weight}
                  </td>
                  <td
                    className={`py-1 text-right font-semibold tabular-nums ${
                      c.contribution > 0
                        ? "text-green-500"
                        : c.contribution < 0
                          ? "text-red-500"
                          : "text-muted-foreground"
                    }`}
                  >
                    {c.contribution >= 0 ? "+" : ""}
                    {c.contribution}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted-foreground">
            Score = suma de aportes (−100 a +100). ALCISTA ≥ +40 · BAJISTA ≤ −40 ·
            VIX ≥ 28 o mercado cerrado ⇒ NO OPERAR. Solo análisis, no ejecuta
            órdenes.
          </p>
        </div>
      )}
    </div>
  )
}
