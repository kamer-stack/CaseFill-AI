import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Normalize Eastern Arabic numerals (۰-۹) to Western digits (0-9) */
export function normalizeNumerals(text: string | null | undefined): string | null {
  if (text == null) return null
  const map: Record<string, string> = {}
  for (let i = 0; i < 10; i++) {
    map[String.fromCharCode(0x0660 + i)] = String(i)
  }
  return text.replace(/[۰-۹]/g, (ch) => map[ch] ?? ch)
}

/** Detect if a string contains Urdu/RTL characters */
export function isRTL(text: string | null | undefined): boolean {
  if (!text) return false
  return /[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]/.test(text)
}

/** Get confidence color class based on score */
export function confidenceColor(score: number | null | undefined): string {
  if (score == null || score === 0) return "bg-red-100 text-red-700 border-red-200"
  if (score >= 0.8) return "bg-green-100 text-green-700 border-green-200"
  return "bg-yellow-100 text-yellow-700 border-yellow-200"
}

/** Get cross-check status color */
export function crossCheckColor(status: string): string {
  switch (status) {
    case "MATCH": return "bg-green-100 text-green-800 border-green-300"
    case "SIMILAR": return "bg-yellow-100 text-yellow-800 border-yellow-300"
    case "MISMATCH": return "bg-red-100 text-red-800 border-red-300"
    default: return "bg-gray-100 text-gray-600 border-gray-300"
  }
}

/** Cross-check icon */
export function crossCheckIcon(status: string): string {
  switch (status) {
    case "MATCH": return "✅"
    case "SIMILAR": return "⚠️"
    case "MISMATCH": return "❌"
    default: return "⚠️"
  }
}
