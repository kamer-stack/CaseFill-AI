import { useEffect, useState, useCallback } from "react"
import { useCase } from "@/context/CaseContext"
import { ALL_SLOTS, DOCUMENT_LABELS } from "@/types"
import type { DocumentSlot } from "@/types"
import { crossCheck, validateField } from "@/lib/api"
import { cn, confidenceColor, crossCheckColor, crossCheckIcon, isRTL, normalizeNumerals } from "@/lib/utils"
import { CheckCircle2, AlertTriangle, XCircle, ChevronLeft, Edit3 } from "lucide-react"

export default function ReviewScreen() {
  const { state, dispatch } = useCase()
  const [activeSlot, setActiveSlot] = useState<DocumentSlot | null>(null)
  const [checking, setChecking] = useState(false)

  // Auto-select first available doc
  useEffect(() => {
    if (!activeSlot) {
      const first = ALL_SLOTS.find(
        (s) => state.documents[s].status === "done" && !state.documents[s].notProvided && state.documents[s].extracted
      )
      if (first) setActiveSlot(first)
    }
  }, [activeSlot, state.documents])

  // Run cross-check whenever extractions change
  const runCrossCheck = useCallback(async () => {
    const docs: Record<string, Record<string, unknown>> = {}
    for (const s of ALL_SLOTS) {
      const d = state.documents[s]
      if (d.extracted) docs[s] = d.extracted
    }
    if (Object.keys(docs).length < 2) return
    setChecking(true)
    try {
      const res = await crossCheck(docs, state.targetChildSerialNumber ?? undefined)
      dispatch({ type: "SET_CROSS_CHECKS", checks: res.checks })
    } catch {
      // silent — cross-check will show stale
    }
    setChecking(false)
  }, [state.documents, state.targetChildSerialNumber, dispatch])

  useEffect(() => {
    runCrossCheck()
  }, [runCrossCheck])

  const handleFieldEdit = async (
    slot: DocumentSlot,
    field: string,
    value: string | null
  ): Promise<{ valid: boolean; error: string | null }> => {
    // Validate via backend before committing
    try {
      const result = await validateField(slot, field, value)
      if (!result.valid) {
        return result  // Return error — FieldRow will show it inline
      }
    } catch {
      // If validation endpoint is unreachable, allow the edit
      // (better to let the FSO work than to block them on a network issue)
    }
    dispatch({ type: "EDIT_FIELD", slot, field, value })
    // Re-run cross-check after a short debounce
    setTimeout(() => runCrossCheck(), 500)
    return { valid: true, error: null }
  }

  const activeDoc = activeSlot ? state.documents[activeSlot] : null
  const completedSlots = ALL_SLOTS.filter(
    (s) => state.documents[s].status === "done" && state.documents[s].extracted
  )
  void completedSlots

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => dispatch({ type: "SET_SCREEN", screen: "upload" })}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ChevronLeft className="w-5 h-5 text-gray-500" />
          </button>
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Review Extractions</h1>
            <p className="text-gray-500 text-sm mt-0.5">Verify and edit extracted data</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {checking && (
            <span className="text-xs text-gray-400 animate-pulse">Re-validating...</span>
          )}
          <button
            onClick={() => dispatch({ type: "SET_SCREEN", screen: "summary" })}
            className="px-5 py-2.5 bg-primary text-white font-medium rounded-xl shadow-sm hover:bg-primary-dark transition-colors"
          >
            Continue to Summary →
          </button>
        </div>
      </div>

      {/* Cross-check summary bar */}
      {state.crossChecks.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {state.crossChecks.map((c, i) => (
            <div
              key={i}
              className={cn(
                "px-3 py-1.5 rounded-full text-xs font-medium border flex items-center gap-1.5",
                crossCheckColor(c.status)
              )}
            >
              <span>{crossCheckIcon(c.status)}</span>
              <span>{c.label}</span>
              {c.status === "SIMILAR" && c.similarity != null && (
                <span className="opacity-70">({Math.round(c.similarity * 100)}%)</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Split view */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: document nav */}
        <div className="col-span-3">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
              <h2 className="text-sm font-semibold text-gray-700">Documents</h2>
            </div>
            <div className="divide-y divide-gray-50">
              {ALL_SLOTS.map((slot) => {
                const doc = state.documents[slot]
                const label = DOCUMENT_LABELS[slot]
                return (
                  <button
                    key={slot}
                    onClick={() => setActiveSlot(slot)}
                    className={cn(
                      "w-full text-left px-4 py-3 flex items-center gap-3 transition-colors",
                      activeSlot === slot ? "bg-primary-50 border-l-3 border-l-primary" : "hover:bg-gray-50"
                    )}
                  >
                    <DocStatusIcon doc={doc} />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{label.en}</p>
                      <p className="text-xs text-gray-400 truncate rtl-text">{label.ur}</p>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Center: image */}
        <div className="col-span-4">
          {activeDoc?.imagePath ? (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
                <h2 className="text-sm font-semibold text-gray-700">
                  {activeSlot && DOCUMENT_LABELS[activeSlot].en}
                </h2>
              </div>
              <div className="p-2">
                <img src={activeDoc.imagePath} alt="Document" className="w-full rounded-lg" />
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8 text-center">
              {activeDoc?.notProvided ? (
                <div className="text-gray-400">
                  <AlertTriangle className="w-10 h-10 mx-auto mb-3 opacity-50" />
                  <p className="text-sm font-medium">Not Provided</p>
                  <p className="text-xs mt-1">This document was marked as not provided</p>
                </div>
              ) : (
                <p className="text-sm text-gray-400">Select a document to review</p>
              )}
            </div>
          )}
        </div>

        {/* Right: extracted fields */}
        <div className="col-span-5">
          {activeDoc?.extracted ? (
            <ExtractedFields
              slot={activeSlot!}
              data={activeDoc.extracted}
              onEdit={handleFieldEdit}
            />
          ) : activeDoc?.notProvided ? (
            <NotProvidedCard slot={activeSlot!} />
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-8 text-center text-sm text-gray-400">
              Select a document to see extracted fields
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Extracted fields panel ─────────────────────────────────────────────── */

function ExtractedFields({
  slot,
  data,
  onEdit,
}: {
  slot: DocumentSlot
  data: Record<string, unknown>
  onEdit: (slot: DocumentSlot, field: string, value: string | null) => void
}) {
  const label = DOCUMENT_LABELS[slot]
  const confidence = (data.confidence as Record<string, number>) ?? {}

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-700">{label.en} — Extracted Fields</h2>
          <p className="text-xs text-gray-400 rtl-text">{label.ur}</p>
        </div>
        <Edit3 className="w-4 h-4 text-gray-400" />
      </div>
      <div className="divide-y divide-gray-50">
        {Object.entries(data)
          .filter(([k]) => !k.startsWith("_") && k !== "confidence" && k !== "children")
          .map(([key, value]) => (
            <FieldRow
              key={key}
              slot={slot}
              fieldKey={key}
              value={value}
              confidence={confidence[key]}
              onEdit={onEdit}
            />
          ))}

        {/* B-form children array */}
        {Array.isArray(data.children) && (
          <div className="p-4">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Children Listed</h3>
            <div className="space-y-3">
              {(data.children as Record<string, unknown>[]).map((child, i) => (
                <div
                  key={i}
                  className={cn(
                    "rounded-lg border p-3",
                    child.is_target_child ? "border-primary bg-primary-50" : "border-gray-200"
                  )}
                >
                  {Boolean(child.is_target_child) && (
                    <span className="text-xs font-semibold text-primary mb-2 block">★ Target Child</span>
                  )}
                  {Object.entries(child)
                    .filter(([k]) => k !== "is_target_child")
                    .map(([k, v]) => (
                      <FieldRow
                        key={k}
                        slot={slot}
                        fieldKey={`children.${i}.${k}`}
                        label={`${k} (#${(child.serial_number as number) ?? i + 1})`}
                        value={v}
                        confidence={undefined}
                        onEdit={onEdit}
                        compact
                      />
                    ))}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── Single field row ────────────────────────────────────────────────────── */

function FieldRow({
  slot,
  fieldKey,
  label,
  value,
  confidence,
  onEdit,
  compact,
}: {
  slot: DocumentSlot
  fieldKey: string
  label?: string
  value: unknown
  confidence?: number
  onEdit: (slot: DocumentSlot, field: string, value: string | null) => Promise<{ valid: boolean; error: string | null }>
  compact?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(String(value ?? ""))
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const displayKey = label ?? fieldKey.split(".").pop() ?? fieldKey
  const displayVal = normalizeNumerals(value != null ? String(value) : null)
  const rtl = isRTL(displayVal)

  const commit = async () => {
    if (saving) return
    if (draft === String(value ?? "")) {
      setEditing(false)
      setError(null)
      return
    }
    setSaving(true)
    try {
      const result = await onEdit(slot, fieldKey, draft || null)
      if (result.valid) {
        setEditing(false)
        setError(null)
      } else {
        setError(result.error ?? "Invalid value")
      }
    } catch (e) {
      setError(String(e))
    }
    setSaving(false)
  }

  const cancel = () => {
    setEditing(false)
    setError(null)
    setDraft(String(value ?? ""))
  }

  return (
    <div className={cn("px-4 py-2.5", compact && "py-1.5")}>
      <div className="flex items-center justify-between gap-2">
        <span className={cn("text-gray-500 capitalize", compact ? "text-xs" : "text-sm")}>
          {displayKey.replace(/_/g, " ")}
        </span>
        {confidence != null && (
          <span
            className={cn(
              "text-xs px-2 py-0.5 rounded-full border font-medium",
              confidenceColor(confidence)
            )}
          >
            {confidence === 0 ? "missing" : `${Math.round(confidence * 100)}%`}
          </span>
        )}
      </div>
      {editing ? (
        <div className="mt-1">
          <input
            autoFocus
            value={draft}
            onChange={(e) => { setDraft(e.target.value); setError(null) }}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit()
              if (e.key === "Escape") cancel()
            }}
            disabled={saving}
            className={cn(
              "w-full px-2 py-1 border rounded text-sm outline-none focus:ring-2",
              error
                ? "border-red-400 focus:ring-red-200 bg-red-50"
                : "border-primary focus:ring-primary/20"
            )}
          />
          {saving && (
            <p className="text-xs text-gray-400 mt-1 animate-pulse">Validating...</p>
          )}
          {error && !saving && (
            <p className="text-xs text-red-600 mt-1">
              <XCircle className="inline w-3 h-3 mr-0.5" />
              {error}
            </p>
          )}
        </div>
      ) : (
        <div
          className="flex items-center gap-2 mt-0.5 cursor-pointer group"
          onClick={() => { setDraft(String(value ?? "")); setEditing(true); setError(null) }}
        >
          {displayVal ? (
            <span
              className={cn(
                rtl ? "rtl-text text-sm" : "text-sm text-gray-900",
                compact && "text-xs"
              )}
            >
              {displayVal}
            </span>
          ) : (
            <span className="text-sm text-gray-300 italic">null</span>
          )}
          <Edit3 className="w-3 h-3 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      )}
    </div>
  )
}

/* ─── Not provided card ───────────────────────────────────────────────────── */

function NotProvidedCard({ slot }: { slot: DocumentSlot }) {
  const label = DOCUMENT_LABELS[slot]
  return (
    <div className="bg-white rounded-xl border border-gray-200 border-dashed shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
        <h2 className="text-sm font-semibold text-gray-700">{label.en}</h2>
        <p className="text-xs text-gray-400 rtl-text">{label.ur}</p>
      </div>
      <div className="p-8 text-center">
        <AlertTriangle className="w-10 h-10 text-gray-300 mx-auto mb-3" />
        <p className="text-sm font-medium text-gray-500">Document Not Provided</p>
        <p className="text-xs text-gray-400 mt-1">
          This slot was intentionally marked as not provided. This is different from an extraction failure.
        </p>
      </div>
    </div>
  )
}

/* ─── Doc status icon ─────────────────────────────────────────────────────── */

function DocStatusIcon({ doc }: { doc: { status: string; notProvided: boolean; extracted: unknown } }) {
  if (doc.notProvided) return <AlertTriangle className="w-4 h-4 text-gray-300 shrink-0" />
  if (doc.status === "done" && doc.extracted) return <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
  if (doc.status === "error") return <XCircle className="w-4 h-4 text-red-400 shrink-0" />
  return <div className="w-4 h-4 rounded-full border-2 border-gray-200 shrink-0" />
}
