import type { CrossCheckResult } from "@/lib/api"

export type DocumentSlot =
  | "child_picture"
  | "result_card"
  | "b_form"
  | "death_certificate"
  | "mother_cnic"
  | "father_cnic"
  | "address"
  | "mother_education"

export type UploadStatus = "empty" | "uploading" | "extracting" | "done" | "error"

export interface DocumentState {
  slot: DocumentSlot
  status: UploadStatus
  file: File | null
  imageId: string | null
  imagePath: string | null
  extracted: Record<string, unknown> | null
  error: string | null
  /** true if the user explicitly skipped this slot */
  notProvided: boolean
}

export interface CaseState {
  documents: Record<DocumentSlot, DocumentState>
  crossChecks: CrossCheckResult[]
  currentScreen: "upload" | "review" | "summary"
  targetChildSerialNumber: number | null
  acknowledgment: string
  submittedCaseId: string | null
}

export const DOCUMENT_LABELS: Record<DocumentSlot, { en: string; ur: string }> = {
  child_picture: { en: "Child's Picture", ur: "بچے کی تصویر" },
  result_card: { en: "School Result Card", ur: "اسکول کا رزلٹ کارڈ" },
  b_form: { en: "Child's B-Form", ur: "بچے کا ب فارم" },
  death_certificate: { en: "Father's Death Certificate", ur: "والد کا ڈیتھ سرٹیفکیٹ" },
  mother_cnic: { en: "Mother's CNIC", ur: "والدہ کا شناختی کارڈ" },
  father_cnic: { en: "Father's CNIC", ur: "والد کا شناختی کارڈ" },
  address: { en: "Address", ur: "پتہ" },
  mother_education: { en: "Mother's Education", ur: "والدہ کی تعلیم" },
}

export const ALL_SLOTS: DocumentSlot[] = [
  "child_picture",
  "result_card",
  "b_form",
  "death_certificate",
  "mother_cnic",
  "father_cnic",
  "address",
  "mother_education",
]
