import { useEffect, useState, type ReactNode } from "react"
import {
  addJournalEntry,
  deleteJournalEntry,
  fetchContracts,
  fetchJournal,
  fetchSignal,
  setJournalOutcome,
  type Analysis,
  type JournalContract,
  type JournalDecision,
  type JournalEntry,
  type JournalOutcome,
} from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

const DECISIONS: { key: JournalDecision; label: string; cls: string }[] = [
  { key: "CALL", label: "📈 CALL", cls: "bg-green-600 hover:bg-green-700 text-white" },
  { key: "PUT", label: "📉 PUT", cls: "bg-red-600 hover:bg-red-700 text-white" },
  { key: "ESPERAR", label: "⏸️ Esperar", cls: "bg-yellow-500 hover:bg-yellow-600 text-black" },
]

const OUTCOMES: { key: JournalOutcome; label: string }[] = [
  { key: "en_curso", label: "⏳ En curso" },
  { key: "acierto", label: "✅ Acierto" },
  { key: "fallo", label: "❌ Fallo" },
  { key: "neutra", label: "➖ Neutra" },
]

function decisionBadge(d: JournalDecision): string {
  if (d === "CALL") return "bg-green-600 text-white"
  if (d === "PUT") return "bg-red-600 text-white"
  return "bg-yellow-500 text-black"
}

function outcomeLabel(o: JournalOutcome): string {
  return OUTCOMES.find((x) => x.key === o)?.label ?? o
}

function fmtTs(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString("es", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
}

export function JournalPanel({
  data,
  onPositionChange,
}: {
  data: Analysis | null
  onPositionChange?: () => void
}) {
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [note, setNote] = useState("")
  const [saving, setSaving] = useState<JournalDecision | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Seguimiento de salida: contrato autocompletado (Paso 4) + prima manual.
  const [attach, setAttach] = useState(true)
  const [cStrike, setCStrike] = useState("")
  const [cExpiry, setCExpiry] = useState("")
  const [cPremium, setCPremium] = useState("")
  const [planStop, setPlanStop] = useState<number | null>(null)
  const [expiries, setExpiries] = useState<string[]>([])

  useEffect(() => {
    fetchJournal()
      .then(setEntries)
      .catch((e) => setError(e instanceof Error ? e.message : "Error"))
  }, [])

  // Al cambiar de ticker: precarga el contrato recomendado y el stop del plan.
  useEffect(() => {
    if (!data?.ticker) return
    let cancel = false
    setCStrike("")
    setCExpiry("")
    setCPremium("")
    setPlanStop(null)
    fetchContracts(data.ticker)
      .then((r) => {
        if (cancel) return
        setExpiries(r.available_expiries)
        if (r.recommended) {
          setCStrike(String(r.recommended.strike))
          setCExpiry(r.expiry ?? "")
          setCPremium(String(r.recommended.mid))
        }
      })
      .catch(() => {})
    fetchSignal(data.ticker)
      .then((s) => {
        if (!cancel) setPlanStop(s.plan?.stop ?? null)
      })
      .catch(() => {})
    return () => {
      cancel = true
    }
  }, [data?.ticker])

  async function registrar(decision: JournalDecision) {
    if (!data) return
    setSaving(decision)
    setError(null)

    // Adjunta el contrato solo en CALL/PUT, si está activado y la prima es válida.
    let contract: JournalContract | null = null
    const premiumNum = Number(cPremium)
    const strikeNum = Number(cStrike)
    if (
      attach &&
      (decision === "CALL" || decision === "PUT") &&
      cExpiry &&
      strikeNum > 0 &&
      premiumNum > 0
    ) {
      contract = {
        type: decision === "CALL" ? "call" : "put",
        strike: strikeNum,
        expiry: cExpiry,
        entry_premium: premiumNum,
        ...(planStop != null ? { stop: planStop } : {}),
      }
    }

    try {
      const created = await addJournalEntry({
        ticker: data.ticker,
        decision,
        price: data.price,
        note: note.trim(),
        context: {
          rsi: data.rsi,
          trend: data.trend,
          classification: data.classification,
        },
        contract,
      })
      setEntries((prev) => [created, ...prev])
      setNote("")
      if (contract) onPositionChange?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error")
    } finally {
      setSaving(null)
    }
  }

  async function cambiarOutcome(id: string, outcome: JournalOutcome) {
    try {
      const updated = await setJournalOutcome(id, outcome)
      setEntries((prev) => prev.map((e) => (e.id === id ? updated : e)))
      // Cerrar una posición (acierto/fallo/neutra) la saca del panel de salida.
      onPositionChange?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error")
    }
  }

  async function eliminar(id: string) {
    try {
      setEntries(await deleteJournalEntry(id))
      onPositionChange?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error")
    }
  }

  // Resumen simple: cuántas decisiones cerradas fueron acierto vs fallo.
  const aciertos = entries.filter((e) => e.outcome === "acierto").length
  const fallos = entries.filter((e) => e.outcome === "fallo").length
  const cerradas = aciertos + fallos
  const winRate = cerradas ? Math.round((aciertos / cerradas) * 100) : null

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 pb-2">
        <CardTitle className="text-sm">
          📓 Diario de decisiones
          <span className="ml-2 font-normal text-muted-foreground">
            · registro manual, no ejecuta órdenes
          </span>
        </CardTitle>
        {winRate != null && (
          <span className="text-xs text-muted-foreground">
            Aciertos: <strong>{winRate}%</strong> ({aciertos}/{cerradas} cerradas)
          </span>
        )}
      </CardHeader>
      <CardContent>
        {error && <p className="mb-2 text-sm text-red-500">⚠️ {error}</p>}

        {/* Registrar nueva decisión */}
        {data ? (
          <div className="mb-4 rounded-lg border border-border bg-muted/30 p-3">
            <p className="mb-2 text-xs text-muted-foreground">
              Decisión sobre <strong>{data.ticker}</strong> a ${data.price} · RSI{" "}
              {data.rsi} · {data.trend}
            </p>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Tu tesis (por qué entrarías o esperarías)…"
              rows={2}
              className="mb-2 w-full resize-none rounded-md border border-border bg-background px-2 py-1.5 text-sm"
            />

            {/* Contrato para seguir la salida (autocompletado del Paso 4 + prima). */}
            <div className="mb-2 rounded-md border border-border bg-background/60 p-2">
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={attach}
                  onChange={(e) => setAttach(e.target.checked)}
                />
                Adjuntar contrato para seguir la salida (+15/+20/+30%, defensa, tesis)
              </label>
              {attach && (
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Field label="Strike">
                    <input
                      type="number"
                      step="0.5"
                      value={cStrike}
                      onChange={(e) => setCStrike(e.target.value)}
                      placeholder="210"
                      className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm"
                    />
                  </Field>
                  <Field label="Vencimiento">
                    {expiries.length > 0 ? (
                      <select
                        value={cExpiry}
                        onChange={(e) => setCExpiry(e.target.value)}
                        className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm"
                      >
                        <option value="">—</option>
                        {expiries.map((d) => (
                          <option key={d} value={d}>
                            {d}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={cExpiry}
                        onChange={(e) => setCExpiry(e.target.value)}
                        placeholder="2026-07-02"
                        className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm"
                      />
                    )}
                  </Field>
                  <Field label="Prima pagada $">
                    <input
                      type="number"
                      step="0.01"
                      value={cPremium}
                      onChange={(e) => setCPremium(e.target.value)}
                      placeholder="7.00"
                      className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm"
                    />
                  </Field>
                  <Field label="Stop (auto)">
                    <div className="px-1 py-1 text-sm tabular-nums text-muted-foreground">
                      {planStop != null ? `$${planStop}` : "—"}
                    </div>
                  </Field>
                </div>
              )}
              {attach && (
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Strike/venc precargados del contrato recomendado; ajusta la prima a lo
                  que realmente pagaste. Solo aplica a CALL/PUT.
                </p>
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              {DECISIONS.map((d) => (
                <Button
                  key={d.key}
                  size="sm"
                  className={d.cls}
                  disabled={saving != null}
                  onClick={() => registrar(d.key)}
                >
                  {saving === d.key ? "Guardando…" : d.label}
                </Button>
              ))}
            </div>
          </div>
        ) : (
          <p className="mb-4 text-sm text-muted-foreground">
            Analiza un ticker para registrar una decisión sobre él.
          </p>
        )}

        {/* Historial */}
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aún no hay decisiones registradas.
          </p>
        ) : (
          <ul className="space-y-2">
            {entries.map((e) => (
              <li
                key={e.id}
                className="rounded-lg border border-border/60 p-3 text-sm"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className={decisionBadge(e.decision)}>{e.decision}</Badge>
                  <span className="font-semibold">{e.ticker}</span>
                  <span className="text-muted-foreground">${e.price}</span>
                  <span className="text-xs text-muted-foreground">
                    · {fmtTs(e.ts)}
                  </span>
                  <span className="ml-auto flex items-center gap-2">
                    <select
                      value={e.outcome}
                      onChange={(ev) =>
                        cambiarOutcome(e.id, ev.target.value as JournalOutcome)
                      }
                      className="rounded-md border border-border bg-background px-1.5 py-0.5 text-xs"
                      title="Marca el resultado para aprender después"
                    >
                      {OUTCOMES.map((o) => (
                        <option key={o.key} value={o.key}>
                          {outcomeLabel(o.key)}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => eliminar(e.id)}
                      className="text-muted-foreground hover:text-red-500"
                      title="Eliminar"
                    >
                      ✕
                    </button>
                  </span>
                </div>
                {e.contract && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    🎟️ {e.contract.type.toUpperCase()} ${e.contract.strike} ·{" "}
                    {e.contract.expiry} · prima ${e.contract.entry_premium}
                    {e.contract.stop != null && ` · stop $${e.contract.stop}`}
                  </p>
                )}
                {e.note && <p className="mt-1.5">{e.note}</p>}
                {e.context && Object.keys(e.context).length > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {Object.entries(e.context)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(" · ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-0.5 text-[10px] uppercase text-muted-foreground">{label}</div>
      {children}
    </div>
  )
}
