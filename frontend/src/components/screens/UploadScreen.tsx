import { useCallback, useState } from "react"
import { useCase } from "@/context/CaseContext"
import { ALL_SLOTS, DOCUMENT_LABELS } from "@/types"
import type { DocumentSlot } from "@/types"
import { uploadImage, extractDocument, saveAddress, saveMotherEducation } from "@/lib/api"
import { CheckCircle2, XCircle, AlertTriangle, ImagePlus, FileText, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

export default function UploadScreen() {
  const { state, dispatch } = useCase()
  const [addressText, setAddressText] = useState("")
  const [motherEducationText, setMotherEducationText] = useState("")

  const doneCount = ALL_SLOTS.filter(
    (s) => state.documents[s].status === "done" || state.documents[s].notProvided
  ).length

  const handleDrop = useCallback(
    async (slot: DocumentSlot, files: FileList | null) => {
      if (!files || files.length === 0) return
      const file = files[0]

      dispatch({ type: "SET_DOC", slot, patch: { file, status: "uploading", error: null } })

      try {
        // Upload
        const up = await uploadImage(file)
        dispatch({ type: "SET_DOC", slot, patch: { imageId: up.image_id, imagePath: up.path, status: "extracting" } })

        // Extract
        const ext = await extractDocument(
          up.image_id,
          slot,
          slot === "b_form" ? (state.targetChildSerialNumber ?? undefined) : undefined
        )
        dispatch({
          type: "SET_DOC",
          slot,
          patch: { extracted: ext.extracted, status: "done" },
        })
      } catch (e) {
        dispatch({ type: "SET_DOC", slot, patch: { status: "error", error: String(e) } })
      }
    },
    [dispatch, state.targetChildSerialNumber]
  )

  const handleAddressSave = async () => {
    if (!addressText.trim()) return
    dispatch({ type: "SET_DOC", slot: "address", patch: { status: "uploading" } })
    try {
      const res = await saveAddress(addressText.trim())
      dispatch({
        type: "SET_DOC",
        slot: "address",
        patch: { extracted: res.extracted, status: "done" },
      })
    } catch (e) {
      dispatch({ type: "SET_DOC", slot: "address", patch: { status: "error", error: String(e) } })
    }
  }

  const handleMotherEducationSave = async () => {
    const value = motherEducationText.trim()
    if (!value) return
    console.log("[MotherEducation] Saving value:", JSON.stringify(value))
    dispatch({ type: "SET_DOC", slot: "mother_education", patch: { status: "uploading" } })
    try {
      const res = await saveMotherEducation(value)
      console.log("[MotherEducation] API response:", JSON.stringify(res))
      dispatch({
        type: "SET_DOC",
        slot: "mother_education",
        patch: { extracted: res.extracted, status: "done" },
      })
    } catch (e) {
      console.error("[MotherEducation] Save failed:", e)
      dispatch({ type: "SET_DOC", slot: "mother_education", patch: { status: "error", error: String(e) } })
    }
  }

  const markNotProvided = (slot: DocumentSlot) => {
    dispatch({ type: "SET_DOC", slot, patch: { notProvided: true, status: "done" } })
  }

  const retrySlot = (slot: DocumentSlot) => {
    dispatch({ type: "SET_DOC", slot, patch: { status: "empty", error: null, extracted: null } })
  }

  /**
   * Open the file picker to replace an already-uploaded image.
   * Old data is NOT cleared until the user actually picks a new file —
   * if they cancel the picker, everything stays as it was.
   */
  const handleReplaceImage = (slot: DocumentSlot) => {
    const input = document.createElement("input")
    input.type = "file"
    input.accept = "image/*,.heic,.heif"
    input.onchange = () => handleDrop(slot, input.files)
    input.click()
  }

  /**
   * Reset a text-based slot (address / mother's education) so the
   * input form reappears. Clears the old saved value.
   */
  const resetTextSlot = (slot: DocumentSlot) => {
    dispatch({
      type: "SET_DOC",
      slot,
      patch: { status: "empty", extracted: null, error: null, notProvided: false },
    })
    if (slot === "address") setAddressText("")
    if (slot === "mother_education") setMotherEducationText("")
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Document Upload</h1>
        <p className="text-gray-500 mt-1">Upload documents for OFSP case verification</p>
      </div>

      {/* Progress */}
      <div className="mb-8 bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">
            {doneCount} of {ALL_SLOTS.length} documents
          </span>
          <span className="text-sm text-gray-400">{Math.round((doneCount / ALL_SLOTS.length) * 100)}%</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2">
          <div
            className="bg-primary h-2 rounded-full transition-all duration-500"
            style={{ width: `${(doneCount / ALL_SLOTS.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Target child selector */}
      <div className="mb-6 bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
        <label className="text-sm font-medium text-gray-700 block mb-2">
          Target child serial number (B-Form row)
        </label>
        <input
          type="number"
          min={1}
          max={10}
          value={state.targetChildSerialNumber ?? ""}
          onChange={(e) =>
            dispatch({ type: "SET_TARGET_CHILD", n: e.target.value ? Number(e.target.value) : null })
          }
          placeholder="e.g. 3"
          className="w-24 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none"
        />
      </div>

      {/* Upload grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {ALL_SLOTS.map((slot) => {
          const doc = state.documents[slot]
          const label = DOCUMENT_LABELS[slot]
          const isAddress = slot === "address"
          const isMotherEducation = slot === "mother_education"
          const isTextInput = isAddress || isMotherEducation

          return (
            <div
              key={slot}
              className={cn(
                "bg-white rounded-xl border shadow-sm overflow-hidden transition-all",
                doc.status === "done" && !doc.notProvided
                  ? "border-primary/30"
                  : doc.notProvided
                    ? "border-gray-200 bg-gray-50"
                    : doc.status === "error"
                      ? "border-red-300"
                      : "border-gray-200"
              )}
            >
              <div className="p-5">
                {/* Label */}
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">{label.en}</h3>
                    <p className="rtl-text text-xs text-gray-500 mt-0.5">{label.ur}</p>
                  </div>
                  <StatusIcon doc={doc} />
                </div>

                {/* Text-based inputs (address & mother's education) */}
                {isTextInput ? (
                  <div>
                    {doc.status === "done" ? (
                      <div className="space-y-2">
                        <div className="bg-primary-50 rounded-lg p-3 text-sm text-primary-dark">
                          <CheckCircle2 className="inline w-4 h-4 mr-1" />
                          {isAddress
                            ? (doc.extracted?.full_address as string)
                            : (doc.extracted?.education_level as string)}
                        </div>
                        <button
                          onClick={() => resetTextSlot(slot)}
                          className="text-xs text-gray-500 hover:text-primary flex items-center gap-1 transition-colors"
                        >
                          <RefreshCw className="w-3 h-3" />
                          Replace
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {isAddress ? (
                          <textarea
                            value={addressText}
                            onChange={(e) => setAddressText(e.target.value)}
                            placeholder="Type the full address here..."
                            rows={2}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none resize-none"
                          />
                        ) : (
                          <select
                            value={motherEducationText}
                            onChange={(e) => setMotherEducationText(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/30 focus:border-primary outline-none"
                          >
                            <option value="">Select education level...</option>
                            <option value="none">None</option>
                            <option value="primary">Primary</option>
                            <option value="middle">Middle</option>
                            <option value="matric">Matric</option>
                            <option value="intermediate">Intermediate</option>
                            <option value="graduate">Graduate</option>
                            <option value="post-graduate">Post-Graduate</option>
                          </select>
                        )}
                        <div className="flex gap-2">
                          <button
                            onClick={isAddress ? handleAddressSave : handleMotherEducationSave}
                            disabled={
                              (isAddress ? !addressText.trim() : !motherEducationText.trim()) ||
                              doc.status === "uploading"
                            }
                            className="px-3 py-1.5 bg-primary text-white text-sm rounded-lg hover:bg-primary-dark disabled:opacity-40 transition-colors"
                          >
                            {doc.status === "uploading" ? "Saving..." : `Save ${isAddress ? "Address" : "Education"}`}
                          </button>
                          <button
                            onClick={() => markNotProvided(slot)}
                            className="px-3 py-1.5 border border-gray-300 text-gray-600 text-sm rounded-lg hover:bg-gray-50 transition-colors"
                          >
                            Not Provided
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ) : doc.status === "done" && !doc.notProvided ? (
                  /* Done state — thumbnail + Replace */
                  <div>
                    <div className="flex items-center gap-3">
                      {doc.imagePath && (
                        <img src={doc.imagePath} alt="" className="w-16 h-16 object-cover rounded-lg border" />
                      )}
                      <div className="text-sm text-primary-dark font-medium">
                        <CheckCircle2 className="inline w-4 h-4 mr-1" />
                        Extracted successfully
                      </div>
                    </div>
                    <button
                      onClick={() => handleReplaceImage(slot)}
                      className="mt-2 text-xs text-gray-500 hover:text-primary flex items-center gap-1 transition-colors"
                    >
                      <RefreshCw className="w-3 h-3" />
                      Replace document
                    </button>
                  </div>
                ) : doc.notProvided ? (
                  /* Not provided state */
                  <div className="text-sm text-gray-400 italic flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    Marked as not provided
                  </div>
                ) : doc.status === "error" ? (
                  /* Error state */
                  <div className="space-y-2">
                    <div className="text-sm text-red-600 bg-red-50 rounded-lg p-2">
                      <XCircle className="inline w-4 h-4 mr-1" />
                      {doc.error?.slice(0, 120)}
                    </div>
                    <button
                      onClick={() => retrySlot(slot)}
                      className="text-sm text-primary hover:underline"
                    >
                      Try again
                    </button>
                  </div>
                ) : (
                  /* Drop zone */
                  <DropZone
                    slot={slot}
                    loading={doc.status === "uploading" || doc.status === "extracting"}
                    loadingLabel={doc.status === "uploading" ? "Uploading..." : "Extracting..."}
                    onDrop={handleDrop}
                    onNotProvided={markNotProvided}
                  />
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Continue button */}
      <div className="mt-8 flex justify-end">
        <button
          onClick={() => dispatch({ type: "SET_SCREEN", screen: "review" })}
          disabled={doneCount === 0}
          className="px-6 py-3 bg-primary text-white font-medium rounded-xl shadow-sm hover:bg-primary-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Continue to Review →
        </button>
      </div>
    </div>
  )
}

function StatusIcon({ doc }: { doc: { status: string; notProvided: boolean } }) {
  if (doc.notProvided) return <AlertTriangle className="w-5 h-5 text-gray-300" />
  switch (doc.status) {
    case "done": return <CheckCircle2 className="w-5 h-5 text-primary" />
    case "uploading":
    case "extracting": return <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
    case "error": return <XCircle className="w-5 h-5 text-red-500" />
    default: return <FileText className="w-5 h-5 text-gray-300" />
  }
}

function DropZone({
  slot,
  loading,
  loadingLabel,
  onDrop,
  onNotProvided,
}: {
  slot: DocumentSlot
  loading: boolean
  loadingLabel: string
  onDrop: (slot: DocumentSlot, files: FileList | null) => void
  onNotProvided: (slot: DocumentSlot) => void
}) {
  const [dragOver, setDragOver] = useState(false)

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); onDrop(slot, e.dataTransfer.files) }}
        className={cn(
          "border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer",
          dragOver ? "border-primary bg-primary-50" : "border-gray-200 hover:border-primary/40",
          loading && "opacity-60 pointer-events-none"
        )}
        onClick={() => {
          if (loading) return
          const input = document.createElement("input")
          input.type = "file"
          input.accept = "image/*,.heic,.heif"
          input.onchange = () => onDrop(slot, input.files)
          input.click()
        }}
      >
        {loading ? (
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-primary font-medium">{loadingLabel}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <ImagePlus className="w-8 h-8 text-gray-300" />
            <p className="text-sm text-gray-500">
              <span className="text-primary font-medium">Click to upload</span> or drag & drop
            </p>
            <p className="text-xs text-gray-400">PNG, JPG, HEIC, WebP</p>
          </div>
        )}
      </div>
      <button
        onClick={() => onNotProvided(slot)}
        className="mt-2 text-xs text-gray-400 hover:text-gray-600 transition-colors"
      >
        Mark as not provided
      </button>
    </div>
  )
}
