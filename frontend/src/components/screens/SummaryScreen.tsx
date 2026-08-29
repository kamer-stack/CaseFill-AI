import { useState } from "react"
import { useCase } from "@/context/CaseContext"
import { ALL_SLOTS, DOCUMENT_LABELS } from "@/types"
import { submitCase } from "@/lib/api"
import { cn, crossCheckColor, crossCheckIcon, confidenceColor, normalizeNumerals } from "@/lib/utils"
import { CheckCircle2, AlertTriangle, XCircle, ChevronLeft, Send, RotateCcw } from "lucide-react"

export default function SummaryScreen() {
  const { state, dispatch } = useCase()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const flagsCount = state.crossChecks.filter(
    (c) => c.status === "MISMATCH" || c.status === "SIMILAR" || c.status === "NEEDS_REVIEW"
  ).length
  const isClean = flagsCount === 0

  const handleSubmit = async () => {
    if (!isClean && !state.acknowledgment.trim()) return
    setSubmitting(true)
    setError(null)

    const documents: Record<string, unknown> = {}
    for (const s of ALL_SLOTS) {
      const d = state.documents[s]
      if (d.extracted) documents[s] = d.extracted
      else if (d.notProvided) documents[s] = { _not_provided: true }
    }

    try {
      const res = await submitCase({
        documents,
        cross_checks: state.crossChecks,
        acknowledgment: state.acknowledgment,
        status: isClean ? "approved" : "submitted_with_flags",
      })
      dispatch({ type: "SET_SUBMITTED", caseId: res.case_id })
    } catch (e) {
      setError(String(e))
    }
    setSubmitting(false)
  }

  // Already submitted
  if (state.submittedCaseId) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-16 text-center">
        <div className="bg-white rounded-2xl border border-primary/20 shadow-lg p-12">
          <CheckCircle2 className="w-16 h-16 text-primary mx-auto mb-6" />
          <h1 className="text-2xl font-semibold text-gray-900 mb-2">Case Submitted</h1>
          <p className="text-gray-500 mb-4">Case ID: <span className="font-mono font-semibold text-primary">{state.submittedCaseId}</span></p>
          {!isClean && (
            <p className="text-sm text-yellow-700 bg-yellow-50 rounded-lg px-4 py-2 inline-block mb-6">
              Submitted with {flagsCount} unresolved flag{flagsCount > 1 ? "s" : ""}
            </p>
          )}
          <div>
            <button
              onClick={() => dispatch({ type: "RESET" })}
              className="px-5 py-2.5 border border-gray-300 text-gray-600 rounded-xl hover:bg-gray-50 transition-colors text-sm"
            >
              <RotateCcw className="inline w-4 h-4 mr-2" />
              Start New Case
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => dispatch({ type: "SET_SCREEN", screen: "review" })}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ChevronLeft className="w-5 h-5 text-gray-500" />
          </button>
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Case Summary</h1>
            <p className="text-gray-500 text-sm mt-0.5">Review all data before submission</p>
          </div>
        </div>
      </div>

      {/* Status banner */}
      <div
        className={cn(
          "rounded-xl p-4 mb-6 flex items-center gap-3",
          isClean ? "bg-green-50 border border-green-200" : "bg-yellow-50 border border-yellow-200"
        )}
      >
        {isClean ? (
          <>
            <CheckCircle2 className="w-6 h-6 text-green-600" />
            <div>
              <p className="font-semibold text-green-800">Ready to submit</p>
              <p className="text-sm text-green-600">All cross-checks passed</p>
            </div>
          </>
        ) : (
          <>
            <AlertTriangle className="w-6 h-6 text-yellow-600" />
            <div>
              <p className="font-semibold text-yellow-800">{flagsCount} item{flagsCount > 1 ? "s" : ""} need{flagsCount === 1 ? "s" : ""} review</p>
              <p className="text-sm text-yellow-600">You can still submit with an acknowledgment</p>
            </div>
          </>
        )}
      </div>

      {/* Cross-check results */}
      {state.crossChecks.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm mb-6 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100 bg-gray-50">
            <h2 className="text-sm font-semibold text-gray-700">Cross-Document Validation</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {state.crossChecks.map((c, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-lg">{crossCheckIcon(c.status)}</span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900">{c.label}</p>
                    {c.detail && <p className="text-xs text-gray-400 truncate">{c.detail}</p>}
                  </div>
                </div>
                <span className={cn("text-xs px-2.5 py-1 rounded-full border font-medium shrink-0", crossCheckColor(c.status))}>
                  {c.status === "SIMILAR" && c.similarity != null
                    ? `SIMILAR (${Math.round(c.similarity * 100)}%)`
                    : c.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Document summaries */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {ALL_SLOTS.map((slot) => {
          const doc = state.documents[slot]
          const label = DOCUMENT_LABELS[slot]

          if (doc.notProvided) {
            return (
              <div key={slot} className="bg-gray-50 rounded-xl border border-gray-200 border-dashed p-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-gray-300" />
                  <h3 className="text-sm font-semibold text-gray-500">{label.en}</h3>
                </div>
                <p className="text-xs text-gray-400 italic">Not provided</p>
              </div>
            )
          }

          if (!doc.extracted) return null

          const data = doc.extracted as Record<string, unknown>
          const conf = (data.confidence as Record<string, number>) ?? {}

          return (
            <div key={slot} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">{label.en}</h3>
              <div className="space-y-1.5">
                {Object.entries(data)
                  .filter(([k]) => k !== "confidence" && k !== "children")
                  .map(([key, val]) => (
                    <div key={key} className="flex items-center justify-between gap-2">
                      <span className="text-xs text-gray-500 capitalize">{key.replace(/_/g, " ")}</span>
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-xs text-gray-900 truncate">
                          {normalizeNumerals(val != null ? String(val) : "—")}
                        </span>
                        {conf[key] != null && (
                          <span className={cn("text-xs px-1.5 py-0.5 rounded-full border", confidenceColor(conf[key]))}>
                            {conf[key] === 0 ? "—" : `${Math.round(conf[key] * 100)}%`}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                {/* Children summary for b_form */}
                {Array.isArray(data.children) && (
                  <div className="mt-2 pt-2 border-t border-gray-100">
                    <span className="text-xs text-gray-500">
                      {(data.children as Record<string, unknown>[]).length} children listed
                      {(data.children as Record<string, unknown>[]).some((c) => c.is_target_child) && (
                        <span className="text-primary font-medium ml-1">
                          (target: #{(data.children as Record<string, unknown>[]).find((c) => c.is_target_child)?.serial_number as number})
                        </span>
                      )}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Acknowledgment */}
      {!isClean && (
        <div className="bg-yellow-50 rounded-xl border border-yellow-200 p-5 mb-6">
          <label className="block text-sm font-semibold text-yellow-800 mb-2">
            Acknowledgment required
          </label>
          <p className="text-xs text-yellow-600 mb-3">
            There are {flagsCount} unresolved flag{flagsCount > 1 ? "s" : ""}. Please provide a brief reason before submitting.
          </p>
          <textarea
            value={state.acknowledgment}
            onChange={(e) => dispatch({ type: "SET_ACKNOWLEDGMENT", text: e.target.value })}
            placeholder="e.g. CNIC number discrepancy confirmed with family via phone call..."
            rows={3}
            className="w-full px-3 py-2 border border-yellow-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-yellow-300 focus:border-yellow-400 outline-none resize-none"
          />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 rounded-xl border border-red-200 p-4 mb-6 text-sm text-red-700">
          <XCircle className="inline w-4 h-4 mr-1" />
          {error}
        </div>
      )}

      {/* Submit */}
      <div className="flex justify-end gap-3">
        <button
          onClick={() => dispatch({ type: "SET_SCREEN", screen: "review" })}
          className="px-5 py-2.5 border border-gray-300 text-gray-600 rounded-xl hover:bg-gray-50 transition-colors"
        >
          ← Back to Review
        </button>
        <button
          onClick={handleSubmit}
          disabled={submitting || (!isClean && !state.acknowledgment.trim())}
          className="px-6 py-2.5 bg-primary text-white font-medium rounded-xl shadow-sm hover:bg-primary-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {submitting ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              Submit Case
            </>
          )}
        </button>
      </div>
    </div>
  )
}
