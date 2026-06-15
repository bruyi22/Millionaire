import { useEffect, useRef } from "react"
import {
  createChart,
  CandlestickSeries,
  LineStyle,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts"
import type { Candle, Levels } from "@/lib/api"

// "2026-06-04 09:30" -> timestamp UTC (asi el eje muestra la hora de mercado tal cual).
function toTs(s: string): UTCTimestamp {
  return (Date.parse(s.replace(" ", "T") + "Z") / 1000) as UTCTimestamp
}

const LEVEL_STYLE: { key: keyof Levels; label: string; color: string }[] = [
  { key: "r2", label: "R2", color: "#f87171" },
  { key: "r1", label: "R1", color: "#ef4444" },
  { key: "pivot", label: "Pivot", color: "#9ca3af" },
  { key: "s1", label: "S1", color: "#22c55e" },
  { key: "s2", label: "S2", color: "#4ade80" },
]

export function CandleChart({
  candles,
  levels,
}: {
  candles: Candle[]
  levels: Levels
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)
  const linesRef = useRef<IPriceLine[]>([])
  const fittedRef = useRef(false)

  // Crear el grafico UNA sola vez (se mantiene entre refrescos).
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 360,
      layout: {
        background: { color: "transparent" },
        textColor: "#a1a1aa",
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      rightPriceScale: { borderColor: "#3f3f46" },
      timeScale: {
        borderColor: "#3f3f46",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: { mode: 0 },
    })

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    })

    chartRef.current = chart
    seriesRef.current = series

    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width
      if (w) chart.applyOptions({ width: w })
    })
    ro.observe(container)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      linesRef.current = []
      fittedRef.current = false
    }
  }, [])

  // Actualizar datos y niveles SIN recrear el grafico (no parpadea, no pierde zoom).
  useEffect(() => {
    const series = seriesRef.current
    const chart = chartRef.current
    if (!series || !chart) return

    series.setData(
      candles.map((c) => ({
        time: toTs(c.time),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    )

    for (const line of linesRef.current) series.removePriceLine(line)
    linesRef.current = []
    for (const lv of LEVEL_STYLE) {
      const price = levels[lv.key]
      if (!price) continue
      linesRef.current.push(
        series.createPriceLine({
          price,
          color: lv.color,
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: lv.label,
        }),
      )
    }

    // Encuadrar solo la primera vez; despues respetamos el zoom del usuario.
    if (!fittedRef.current) {
      chart.timeScale().fitContent()
      fittedRef.current = true
    }
  }, [candles, levels])

  return <div ref={containerRef} className="w-full" />
}
