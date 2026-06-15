import { useState, type ReactNode } from "react"
import { fetchAnalysis, type Analysis } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { WatchlistPanel } from "@/components/WatchlistPanel"
import { OptionsPanel } from "@/components/OptionsPanel"
import { IntradayPanel } from "@/components/IntradayPanel"
import { JournalPanel } from "@/components/JournalPanel"
import { MarketRegimeBanner } from "@/components/MarketRegimeBanner"
import { OpeningPanel } from "@/components/OpeningPanel"
import { SignalPanel } from "@/components/SignalPanel"
import { ExitPanel } from "@/components/ExitPanel"
import { RankingPanel } from "@/components/RankingPanel"
import { JournalStatsPanel } from "@/components/JournalStatsPanel"

function classificationClasses(c: string): string {
  switch (c) {
    case "Alta":
      return "bg-green-600 text-white"
    case "Riesgosa":
      return "bg-red-600 text-white"
    default:
      return "bg-yellow-500 text-black"
  }
}

function trendEmoji(trend: string): string {
  if (trend === "Alcista") return "📈"
  if (trend === "Bajista") return "📉"
  return "➡️"
}

function Stat({
  label,
  value,
  hint,
  valueClass,
}: {
  label: string
  value: ReactNode
  hint?: string
  valueClass?: string
}) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-bold ${valueClass ?? ""}`}>{value}</div>
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  )
}

function rsiClass(rsi: number): string {
  if (rsi >= 70) return "text-red-500"
  if (rsi <= 30) return "text-yellow-500"
  return "text-green-500"
}

export default function App() {
  const [ticker, setTicker] = useState("KO")
  const [data, setData] = useState<Analysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Cambia al registrar/cerrar una posición → fuerza recarga del panel de salida.
  const [positionsKey, setPositionsKey] = useState(0)

  async function handleAnalyze(symbol: string = ticker) {
    const sym = symbol.trim().toUpperCase()
    if (!sym) return
    setTicker(sym)
    setLoading(true)
    setError(null)
    try {
      const result = await fetchAnalysis(sym)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido")
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-5xl">
        {/* Header */}
        <header className="mb-6">
          <h1 className="text-3xl font-bold tracking-tight">
            💹 Millionaire
          </h1>
          <p className="text-sm text-muted-foreground">
            Soporte de decisiones · solo análisis, no ejecuta órdenes
          </p>
        </header>

        {/* Régimen de mercado: ¿permite operar hoy? (lo primero que se ve) */}
        <div className="mb-6">
          <MarketRegimeBanner />
        </div>

        {/* Buscador */}
        <div className="mb-8 flex gap-2">
          <Input
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            placeholder="Ticker (ej: KO, AAPL, MSFT)"
            className="max-w-xs"
          />
          <Button onClick={() => handleAnalyze()} disabled={loading}>
            {loading ? "Analizando..." : "Analizar"}
          </Button>
        </div>

        {/* Watchlist */}
        <div className="mb-8">
          <WatchlistPanel active={data?.ticker} onSelect={(t) => handleAnalyze(t)} />
        </div>

        {/* Ranking de oportunidades: ¿dónde hay ventaja hoy? (global, automático) */}
        <div className="mb-8">
          <RankingPanel onSelect={(t) => handleAnalyze(t)} />
        </div>

        {/* Salida: posiciones abiertas que estás gestionando ahora (global) */}
        <div className="mb-8">
          <ExitPanel refreshKey={positionsKey} />
        </div>

        {/* Estadísticas del diario: ¿qué te funciona? (global, review/aprendizaje) */}
        <div className="mb-8">
          <JournalStatsPanel refreshKey={positionsKey} />
        </div>

        {error && (
          <Card className="mb-6 border-red-600/50">
            <CardContent className="py-4 text-red-500">⚠️ {error}</CardContent>
          </Card>
        )}

        {data && (
          <div className="space-y-6">
            {/* Encabezado del ticker */}
            <Card>
              <CardContent className="flex flex-wrap items-center justify-between gap-4 py-5">
                <div>
                  <div className="flex items-center gap-3">
                    <span className="text-2xl font-bold">{data.ticker}</span>
                    <Badge className={classificationClasses(data.classification)}>
                      {data.classification}
                    </Badge>
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    {trendEmoji(data.trend)} Tendencia: {data.trend}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-bold">${data.price}</div>
                  <div
                    className={`text-sm font-medium ${
                      data.distance_from_open_pct >= 0
                        ? "text-green-500"
                        : "text-red-500"
                    }`}
                  >
                    {data.distance_from_open_pct >= 0 ? "▲" : "▼"}{" "}
                    {data.distance_from_open_pct}% desde apertura
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Señal estructurada: ¿hay ventaja? (determinista, GRATIS) */}
            <SignalPanel ticker={data.ticker} />

            {/* Módulo de apertura 9:30-10:00 (disciplina, GRATIS) */}
            <OpeningPanel ticker={data.ticker} />

            {/* Velas intradia en vivo + disparadores */}
            <IntradayPanel ticker={data.ticker} />

            {/* Cadena de opciones */}
            <OptionsPanel ticker={data.ticker} />

            {/* Tarjetas de indicadores */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
              <Stat
                label="RSI (14)"
                value={data.rsi}
                valueClass={rsiClass(data.rsi)}
                hint={
                  data.rsi >= 70
                    ? "Sobrecompra"
                    : data.rsi <= 30
                      ? "Sobreventa"
                      : "Neutral"
                }
              />
              <Stat
                label="MACD"
                value={data.macd}
                hint={`Señal ${data.macd_signal} · hist ${data.macd_hist}`}
                valueClass={
                  data.macd_hist >= 0 ? "text-green-500" : "text-red-500"
                }
              />
              <Stat
                label="Volumen"
                value={`${data.volume_ratio}x`}
                hint="vs promedio 20d"
                valueClass={
                  data.volume_ratio >= 1.5
                    ? "text-green-500"
                    : data.volume_ratio < 0.7
                      ? "text-red-500"
                      : ""
                }
              />
              <Stat
                label="ATR"
                value={`${data.atr_pct}%`}
                hint={`Rango día ${data.day_range_pct}%`}
              />
              <Stat label="SMA 20" value={data.sma20} />
              <Stat label="SMA 50" value={data.sma50} />
              <Stat label="SMA 200" value={data.sma200} />
              <Stat
                label="Apertura"
                value={`$${data.day_open}`}
                hint={`Cierre prev. $${data.prev_close}`}
              />
            </div>

            {/* Pros / Contras / Banderas */}
            <div className="grid gap-4 md:grid-cols-3">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-green-500">
                    ✅ A favor
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {data.pros.length ? (
                      data.pros.map((p, i) => <li key={i}>• {p}</li>)
                    ) : (
                      <li>—</li>
                    )}
                  </ul>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-yellow-500">
                    ⚠️ En contra
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {data.cons.length ? (
                      data.cons.map((c, i) => <li key={i}>• {c}</li>)
                    ) : (
                      <li>—</li>
                    )}
                  </ul>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-red-500">
                    🚨 Banderas de riesgo
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {data.flags.length ? (
                      data.flags.map((f, i) => <li key={i}>• {f}</li>)
                    ) : (
                      <li>Sin banderas</li>
                    )}
                  </ul>
                </CardContent>
              </Card>
            </div>

            {/* Diario de decisiones (registro manual) */}
            <JournalPanel
              data={data}
              onPositionChange={() => setPositionsKey((k) => k + 1)}
            />
          </div>
        )}

        {!data && !error && !loading && (
          <p className="text-sm text-muted-foreground">
            Busca un ticker para ver su análisis técnico en vivo.
          </p>
        )}
      </div>
    </div>
  )
}
