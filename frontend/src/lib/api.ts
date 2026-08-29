const BASE = "/api"

export interface UploadResponse {
  image_id: string
  path: string
  filename: string
}

export interface ExtractResponse {
  document_type: string
  extracted: Record<string, unknown>
  image_path: string
  timestamp: string
}

export interface CrossCheckResult {
  label: string
  source: { doc: string; field: string }
  target: { doc: string; field: string }
  status: "MATCH" | "SIMILAR" | "MISMATCH" | "NEEDS_REVIEW"
  detail: string | null
  similarity: number | null
}

export interface CrossCheckResponse {
  checks: CrossCheckResult[]
}

export interface SubmitResponse {
  case_id: string
  status: string
  submitted_at: string
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, options)
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`API error ${res.status}: ${body}`)
  }
  return res.json()
}

export async function uploadImage(file: File): Promise<UploadResponse> {
  const fd = new FormData()
  fd.append("file", file)
  return request<UploadResponse>("/upload", { method: "POST", body: fd })
}

export async function extractDocument(
  imageId: string,
  documentType: string,
  targetChildSerialNumber?: number
): Promise<ExtractResponse> {
  const fd = new FormData()
  fd.append("image_id", imageId)
  fd.append("document_type", documentType)
  if (targetChildSerialNumber != null) {
    fd.append("target_child_serial_number", String(targetChildSerialNumber))
  }
  return request<ExtractResponse>("/extract", { method: "POST", body: fd })
}

export async function saveAddress(fullAddress: string): Promise<ExtractResponse> {
  const fd = new FormData()
  fd.append("full_address", fullAddress)
  return request<ExtractResponse>("/save-address", { method: "POST", body: fd })
}

export async function saveMotherEducation(educationLevel: string): Promise<ExtractResponse> {
  const fd = new FormData()
  fd.append("education_level", educationLevel)
  return request<ExtractResponse>("/save-mother-education", { method: "POST", body: fd })
}

export async function crossCheck(
  documents: Record<string, Record<string, unknown>>,
  targetChildSerialNumber?: number
): Promise<CrossCheckResponse> {
  return request<CrossCheckResponse>("/cross-check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ documents, target_child_serial_number: targetChildSerialNumber }),
  })
}

export async function submitCase(data: {
  documents: Record<string, unknown>
  cross_checks: CrossCheckResult[]
  acknowledgment: string
  status: string
}): Promise<SubmitResponse> {
  return request<SubmitResponse>("/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
}
