import { createContext, useContext, useReducer, useEffect, type ReactNode } from "react"
import type { CaseState, DocumentSlot, DocumentState } from "@/types"
import { ALL_SLOTS } from "@/types"
import type { CrossCheckResult } from "@/lib/api"

const STORAGE_KEY = "ofsp_case_state"

function makeInitialDoc(slot: DocumentSlot): DocumentState {
  return { slot, status: "empty", file: null, imageId: null, imagePath: null, extracted: null, error: null, notProvided: false }
}

function makeInitialState(): CaseState {
  const docs = {} as Record<DocumentSlot, DocumentState>
  for (const s of ALL_SLOTS) docs[s] = makeInitialDoc(s)
  return {
    documents: docs,
    crossChecks: [],
    currentScreen: "upload",
    targetChildSerialNumber: null,
    acknowledgment: "",
    submittedCaseId: null,
  }
}

/** Strip non-serializable File objects before saving to localStorage */
function serialize(state: CaseState): string {
  const docs = {} as Record<string, unknown>
  for (const [k, v] of Object.entries(state.documents)) {
    docs[k] = { ...v, file: null }
  }
  return JSON.stringify({ ...state, documents: docs })
}

function loadState(): CaseState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return makeInitialState()
    const parsed = JSON.parse(raw) as CaseState
    // Re-add file: null for each doc
    for (const s of ALL_SLOTS) {
      if (!parsed.documents[s]) parsed.documents[s] = makeInitialDoc(s)
      parsed.documents[s].file = null
    }
    return parsed
  } catch {
    return makeInitialState()
  }
}

type Action =
  | { type: "SET_SCREEN"; screen: CaseState["currentScreen"] }
  | { type: "SET_DOC"; slot: DocumentSlot; patch: Partial<DocumentState> }
  | { type: "SET_CROSS_CHECKS"; checks: CrossCheckResult[] }
  | { type: "SET_TARGET_CHILD"; n: number | null }
  | { type: "SET_ACKNOWLEDGMENT"; text: string }
  | { type: "SET_SUBMITTED"; caseId: string }
  | { type: "EDIT_FIELD"; slot: DocumentSlot; field: string; value: string | null }
  | { type: "RESET" }

function reducer(state: CaseState, action: Action): CaseState {
  switch (action.type) {
    case "SET_SCREEN":
      return { ...state, currentScreen: action.screen }

    case "SET_DOC":
      return {
        ...state,
        documents: { ...state.documents, [action.slot]: { ...state.documents[action.slot], ...action.patch } },
      }

    case "SET_CROSS_CHECKS":
      return { ...state, crossChecks: action.checks }

    case "SET_TARGET_CHILD":
      return { ...state, targetChildSerialNumber: action.n }

    case "SET_ACKNOWLEDGMENT":
      return { ...state, acknowledgment: action.text }

    case "SET_SUBMITTED":
      return { ...state, submittedCaseId: action.caseId }

    case "EDIT_FIELD": {
      const doc = { ...state.documents[action.slot] }
      if (doc.extracted) {
        doc.extracted = { ...doc.extracted, [action.field]: action.value }
      }
      return { ...state, documents: { ...state.documents, [action.slot]: doc } }
    }

    case "RESET":
      localStorage.removeItem(STORAGE_KEY)
      return makeInitialState()

    default:
      return state
  }
}

interface Ctx {
  state: CaseState
  dispatch: React.Dispatch<Action>
}

const CaseCtx = createContext<Ctx | null>(null)

export function CaseProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, loadState)

  // Persist to localStorage on every change
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, serialize(state))
  }, [state])

  return <CaseCtx.Provider value={{ state, dispatch }}>{children}</CaseCtx.Provider>
}

export function useCase() {
  const ctx = useContext(CaseCtx)
  if (!ctx) throw new Error("useCase must be used within CaseProvider")
  return ctx
}
