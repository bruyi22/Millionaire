// Cliente de la API del backend (FastAPI). Tipos espejo de core/analysis.py.
// App 100% determinista: sin IA (no hay tipos ni llamadas a OpenAI).

export interface Analysis {
  ticker: string
  price: number
  day_open: number
  prev_close: number
  distance_from_open_pct: number
  day_range_pct: number
  rsi: number
  macd: number
  macd_signal: number
  macd_hist: number
  sma20: number
  sma50: number
  sma200: number
  volume: number
  avg_volume20: number
  volume_ratio: number
  atr: number
  atr_pct: number
  flags: string[]
  pros: string[]
  cons: string[]
  classification: string
  trend: string
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000"

export async function fetchAnalysis(ticker: string): Promise<Analysis> {
  const res = await fetch(
    `${API_BASE}/analyze/${encodeURIComponent(ticker.trim())}`,
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json() as Promise<Analysis>
}

export interface OptionContract {
  type: "call" | "put"
  strike: number
  last: number
  bid: number
  ask: number
  mid: number
  spread_pct: number
  volume: number
  open_interest: number
  iv: number
  in_the_money: boolean
  moneyness_pct: number
  break_even: number
  break_even_move_pct: number
  be_em_ratio: number | null
  delta: number
  gamma: number
  theta: number
  vega: number
  flags: string[]
}

export interface OptionChain {
  ticker: string
  underlying_price: number
  expiry: string
  dte: number | null
  available_expiries: string[]
  expected_move: number | null
  expected_move_pct: number | null
  em_method: "straddle" | "iv" | null
  calls: OptionContract[]
  puts: OptionContract[]
}

export async function fetchOptions(
  ticker: string,
  expiry?: string,
  strikes = 6,
): Promise<OptionChain> {
  const params = new URLSearchParams({ strikes: String(strikes) })
  if (expiry) params.set("expiry", expiry)
  const res = await fetch(
    `${API_BASE}/options/${encodeURIComponent(ticker.trim())}?${params}`,
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json() as Promise<OptionChain>
}

export interface Candle {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface Levels {
  pivot: number
  r1: number
  r2: number
  s1: number
  s2: number
  day_open: number
  day_high: number
  day_low: number
  prev_close: number
  sma20: number
  sma50: number
  sma200: number
}

export interface Trigger {
  level: string
  price: number
  distance_pct: number
}

export interface QuickTriggers {
  bias: "CALL" | "PUT" | "NEUTRAL"
  call: Trigger | null
  put: Trigger | null
}

export interface IntradayData {
  ticker: string
  interval: string
  current_price: number
  candles: Candle[]
  levels: Levels
  triggers: QuickTriggers
}

export async function fetchIntraday(
  ticker: string,
  interval = "5m",
): Promise<IntradayData> {
  const res = await fetch(
    `${API_BASE}/intraday/${encodeURIComponent(ticker.trim())}?interval=${interval}`,
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json() as Promise<IntradayData>
}

// --------------------------------------------------------------------------- //
//  Market Regime Score: ¿el mercado permite operar hoy? (GRATIS, sin IA)
// --------------------------------------------------------------------------- //
export interface RegimeComponent {
  name: string
  weight: number
  vote: number
  contribution: number
  detail: string
}

export interface MarketRegime {
  regime: "ALCISTA" | "BAJISTA" | "MIXTO" | "NO OPERAR"
  score: number
  market_open: boolean
  veto_reason: string | null
  vix_level: number | null
  vix_label: string | null
  summary: string
  breakdown: RegimeComponent[]
  errors: Record<string, string> | null
  ts: string
}

export async function fetchMarketRegime(): Promise<MarketRegime> {
  const res = await fetch(`${API_BASE}/market-regime`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json() as Promise<MarketRegime>
}

// --------------------------------------------------------------------------- //
//  Módulo de apertura 9:30-10:00 ET (GRATIS, sin IA)
// --------------------------------------------------------------------------- //
export interface OpeningAnalysis {
  ticker: string
  session_date: string
  live: boolean
  interval: string
  phase: "OBSERVAR" | "CONFIRMANDO" | "DECISION"
  phase_label: string
  opening_range: { high: number; low: number }
  vwap: number
  current_price: number
  above_vwap: boolean
  gap_pct: number
  premarket_bias: "alcista" | "bajista" | "neutral"
  bias: "CALL" | "PUT" | "NEUTRAL"
  signal: "CALL" | "PUT" | "NO OPERAR" | "ESPERAR" | "OBSERVAR"
  confidence: "alta" | "media" | "baja"
  events: string[]
  narrative: string
  note: string
  candles_in_opening: number
}

export async function fetchOpening(ticker: string): Promise<OpeningAnalysis> {
  const res = await fetch(
    `${API_BASE}/opening/${encodeURIComponent(ticker.trim())}`,
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json() as Promise<OpeningAnalysis>
}

// --------------------------------------------------------------------------- //
//  Señal estructurada CALL/PUT/NO OPERAR (motor de confluencias, GRATIS)
// --------------------------------------------------------------------------- //
export interface SignalPlan {
  setup_level: number
  entry: number
  stop: number
  target1: number
  target2: number
  rr: number
  entry_distance_pct: number
  entry_distance_atr: number
  proximity_state: "pegado" | "cerca" | "lejos" | "extendido"
  proximity_label: string
  proximity_factor: number
}

export interface SignalFactor {
  factor: string
  weight: number
  vote: "CALL" | "PUT" | "—"
  detail: string
}

export interface SignalSession {
  session_state:
    | "apertura"
    | "media-manana"
    | "mediodia"
    | "media-tarde"
    | "cierre"
    | "cerrado"
  session_label: string
  session_factor: number
  et_time: string
}

export interface DecisionSignal {
  ticker: string
  price: number
  signal: "CALL" | "PUT" | "NO OPERAR"
  direction: "CALL" | "PUT" | "NEUTRAL"
  confidence: number
  agreement: number
  net_score: number
  plan: SignalPlan | null
  contract_hint: string | null
  reason: string
  risk: string
  veto_reason: string | null
  factors: SignalFactor[]
  session: SignalSession
  context: {
    trend: string
    classification: string
    rsi: number
    atr: number
    volume_ratio: number
    regime: string | null
    opening_signal: string | null
    above_vwap: boolean | null
  }
}

export async function fetchSignal(ticker: string): Promise<DecisionSignal> {
  const res = await fetch(
    `${API_BASE}/signal/${encodeURIComponent(ticker.trim())}`,
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json() as Promise<DecisionSignal>
}

// --------------------------------------------------------------------------- //
//  Contrato recomendado (scorer de la cadena, GRATIS sin IA)
// --------------------------------------------------------------------------- //
export interface ScoredContract {
  strike: number
  type: "call" | "put"
  delta: number
  spread_pct: number
  open_interest: number
  volume: number
  iv: number
  mid: number
  break_even: number
  break_even_move_pct: number
  be_em_ratio: number | null
  theta: number
  score: number
  category: "Recomendado" | "Agresivo" | "Viable" | "Evitar"
  reasons: string[]
}

export interface ContractRecommendation {
  ticker: string
  direction: "CALL" | "PUT" | "NEUTRAL" | string
  signal_state: string | null
  expiry: string | null
  dte: number | null
  underlying_price: number | null
  available_expiries: string[]
  expected_move: number | null
  expected_move_pct: number | null
  em_method: "straddle" | "iv" | null
  recommended: ScoredContract | null
  aggressive: ScoredContract | null
  avoid: ScoredContract[]
  scored: ScoredContract[]
  earnings_warning: boolean
  earnings_date: string | null
  note: string
}

export async function fetchContracts(
  ticker: string,
  direction?: string,
  expiry?: string,
): Promise<ContractRecommendation> {
  const params = new URLSearchParams()
  if (direction) params.set("direction", direction)
  if (expiry) params.set("expiry", expiry)
  const qs = params.toString()
  const res = await fetch(
    `${API_BASE}/contracts/${encodeURIComponent(ticker.trim())}${qs ? `?${qs}` : ""}`,
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json() as Promise<ContractRecommendation>
}

export async function getWatchlist(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/watchlist`)
  return res.json() as Promise<string[]>
}

export interface WatchlistStatus {
  ticker: string
  classification: string | null
  trend: string | null
  price: number | null
  distance_from_open_pct: number | null
  error: string | null
}

export async function fetchWatchlistStatus(): Promise<WatchlistStatus[]> {
  const res = await fetch(`${API_BASE}/watchlist/status`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json() as Promise<WatchlistStatus[]>
}

export async function addToWatchlist(ticker: string): Promise<string[]> {
  const res = await fetch(
    `${API_BASE}/watchlist/${encodeURIComponent(ticker.trim())}`,
    { method: "POST" },
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json() as Promise<string[]>
}

export async function removeFromWatchlist(ticker: string): Promise<string[]> {
  const res = await fetch(
    `${API_BASE}/watchlist/${encodeURIComponent(ticker.trim())}`,
    { method: "DELETE" },
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json() as Promise<string[]>
}

// --------------------------------------------------------------------------- //
//  Diario de decisiones (registro manual, NO ejecuta ordenes)
// --------------------------------------------------------------------------- //
export type JournalDecision = "CALL" | "PUT" | "ESPERAR"
export type JournalOutcome = "en_curso" | "acierto" | "fallo" | "neutra"

// Contrato adjunto a una posición para el seguimiento de salida (Paso 5).
export interface JournalContract {
  type: "call" | "put"
  strike: number
  expiry: string
  entry_premium: number
  stop?: number
}

export interface JournalEntry {
  id: string
  ts: string
  ticker: string
  decision: JournalDecision
  price: number
  note: string
  context: Record<string, string | number>
  contract?: JournalContract | null
  outcome: JournalOutcome
}

export interface NewJournalEntry {
  ticker: string
  decision: JournalDecision
  price?: number
  note?: string
  context?: Record<string, string | number>
  contract?: JournalContract | null
}

export async function fetchJournal(): Promise<JournalEntry[]> {
  const res = await fetch(`${API_BASE}/journal`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json() as Promise<JournalEntry[]>
}

export async function addJournalEntry(
  entry: NewJournalEntry,
): Promise<JournalEntry> {
  const res = await fetch(`${API_BASE}/journal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entry),
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json() as Promise<JournalEntry>
}

export async function setJournalOutcome(
  id: string,
  outcome: JournalOutcome,
): Promise<JournalEntry> {
  const res = await fetch(`${API_BASE}/journal/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ outcome }),
  })
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Error ${res.status}`)
  }
  return res.json() as Promise<JournalEntry>
}

export async function deleteJournalEntry(id: string): Promise<JournalEntry[]> {
  const res = await fetch(`${API_BASE}/journal/${id}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json() as Promise<JournalEntry[]>
}

// --------------------------------------------------------------------------- //
//  Estadísticas del diario (solo conteo: win-rate, rachas, ticker, hora)
// --------------------------------------------------------------------------- //
export interface StatTickerRow {
  ticker: string
  total: number
  wins: number
  losses: number
  neutral: number
  open: number
  win_rate: number | null
}

export interface StatHourRow {
  hour: number
  label: string
  total: number
  wins: number
  losses: number
  neutral: number
  open: number
  win_rate: number | null
}

export interface JournalStats {
  generated_at: string
  total: number
  open: number
  closed: number
  wins: number
  losses: number
  neutral: number
  win_rate: number | null
  streak: { type: "acierto" | "fallo" | null; count: number }
  best_win_streak: number
  worst_loss_streak: number
  by_ticker: StatTickerRow[]
  by_hour: StatHourRow[]
}

export async function fetchJournalStats(): Promise<JournalStats> {
  const res = await fetch(`${API_BASE}/journal/stats`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json() as Promise<JournalStats>
}

// --------------------------------------------------------------------------- //
//  Módulo de salida: posiciones abiertas + señal de salida (GRATIS, sin IA)
// --------------------------------------------------------------------------- //
export interface Position {
  id: string
  ticker: string
  decision: "CALL" | "PUT"
  type: "call" | "put"
  strike: number
  expiry: string
  entry_premium: number
  stop: number | null
  note: string
  ts: string
  underlying_price?: number
  current_premium?: number
  pnl_pct?: number
  dte?: number | null
  iv?: number
  theta?: number
  spread_pct?: number
  thesis_broken?: boolean
  signal:
    | "MANTENER"
    | "GANANCIA_15"
    | "GANANCIA_20"
    | "GANANCIA_30"
    | "DEFENSIVA"
    | "SALIR"
    | "VIGILA_TIEMPO"
    | null
  signal_label?: string
  tone?: "verde" | "rojo" | "amarillo" | "neutro"
  action?: string
  error: string | null
}

export async function fetchPositions(): Promise<Position[]> {
  const res = await fetch(`${API_BASE}/positions`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json() as Promise<Position[]>
}

// --------------------------------------------------------------------------- //
//  Ranking de oportunidades: ¿dónde hay ventaja hoy? (GRATIS, sin IA)
// --------------------------------------------------------------------------- //
export interface RankingContract {
  type: "call" | "put"
  strike: number
  delta: number
  mid: number
  score: number
  earnings_warning: boolean
}

export interface RankingPlan {
  entry: number
  stop: number
  target1: number
  target2: number
  rr: number
}

export interface OpportunityRow {
  ticker: string
  price?: number
  signal: "CALL" | "PUT" | "NO OPERAR" | null
  direction?: "CALL" | "PUT" | "NEUTRAL"
  confidence?: number
  agreement?: number
  reason?: string
  veto_reason?: string | null
  plan?: RankingPlan | null
  contract?: RankingContract | null
  category?: "Mejor" | "Segunda" | "Esperar" | "Error"
  score: number
  error: string | null
}

export interface RankingResult {
  ts: string
  regime: {
    regime: string | null
    score: number | null
    veto_reason: string | null
  }
  best: OpportunityRow | null
  count_actionable: number
  count_total: number
  ranked: OpportunityRow[]
}

export async function fetchRanking(): Promise<RankingResult> {
  const res = await fetch(`${API_BASE}/ranking`)
  if (!res.ok) throw new Error(`Error ${res.status}`)
  return res.json() as Promise<RankingResult>
}
