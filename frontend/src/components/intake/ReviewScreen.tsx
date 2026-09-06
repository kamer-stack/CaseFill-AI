import React, { useState, useEffect, useCallback } from 'react';
import { DocumentSlotConfig, CrossCheckResult, DocType, INITIAL_DOCUMENT_SLOTS } from '../../types';
import { casesApi } from '../../lib/api';
import { getFieldRule } from '../../lib/fieldValidation';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ChevronLeft,
  ArrowRight,
  Edit3,
  RefreshCw,
} from 'lucide-react';

interface ReviewScreenProps {
  slots: DocumentSlotConfig[];
  extractedData: Record<string, any>;
  setExtractedData: React.Dispatch<React.SetStateAction<Record<string, any>>>;
  crossChecks: CrossCheckResult[];
  setCrossChecks: React.Dispatch<React.SetStateAction<CrossCheckResult[]>>;
  caseId: string;
  onProceed: () => void;
  onBack: () => void;
  isDualLanguage: boolean;
}

// ── Cross-check display helpers ────────────────────────────────────────────

const checkColor = (s: string) => {
  switch (s) {
    case 'MATCH': return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    case 'SIMILAR': return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'MISMATCH': return 'bg-rose-50 text-rose-700 border-rose-200';
    case 'NEEDS_REVIEW': return 'bg-orange-50 text-orange-700 border-orange-200';
    case 'DIFFERENT_SCRIPT': return 'bg-violet-50 text-violet-700 border-violet-200';
    default: return 'bg-slate-50 text-slate-700 border-slate-200';
  }
};

const checkIcon = (s: string) => {
  switch (s) {
    case 'MATCH': return '✓';
    case 'SIMILAR': return '~';
    case 'MISMATCH': return '✗';
    case 'NEEDS_REVIEW': return '?';
    case 'DIFFERENT_SCRIPT': return '⚡';
    default: return '•';
  }
};

const confidenceColor = (c: number) => {
  if (c >= 0.9) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (c >= 0.7) return 'bg-amber-50 text-amber-700 border-amber-200';
  if (c === 0) return 'bg-slate-50 text-slate-400 border-slate-200';
  return 'bg-rose-50 text-rose-700 border-rose-200';
};

// Solid dot color matching the confidence tier (green / yellow / red)
const confidenceDot = (c: number) => {
  if (c >= 0.9) return 'bg-emerald-500';
  if (c >= 0.7) return 'bg-amber-500';
  if (c === 0) return 'bg-slate-300';
  return 'bg-rose-500';
};

// Left accent bar for field rows with weak extractions.
// confidence === 0 (missing/needs-review) gets the STRONGEST treatment —
// it was previously grouped with high-confidence fields and got no accent
// at all, which is why review-needed fields didn't stand out.
const confidenceRowAccent = (c: number | undefined) => {
  if (c == null) return '';
  if (c === 0) return 'border-l-[3px] border-l-rose-400 bg-rose-50/40';
  if (c >= 0.9) return '';
  if (c >= 0.7) return 'border-l-[3px] border-l-amber-300';
  return 'border-l-[3px] border-l-rose-400';
};

const isRTL = (text: string | null) => {
  if (!text) return false;
  return /[\u0600-\u06FF\u0750-\u077F]/.test(text);
};

// A document needs review when any extracted field's confidence score is
// missing (null/undefined/absent) or zero (rendered as "missing" on field rows).
const hasMissingConfidence = (data: any): boolean => {
  if (!data || typeof data !== 'object') return false;
  const conf = (data.confidence ?? {}) as Record<string, any>;
  return Object.entries(data)
    .filter(([k]) => !k.startsWith('_') && k !== 'confidence' && k !== 'children')
    .some(([k]) => {
      const c = conf[k];
      return c == null || c === '' || c === 0;
    });
};

export const ReviewScreen: React.FC<ReviewScreenProps> = ({
  slots,
  extractedData,
  setExtractedData,
  crossChecks,
  setCrossChecks,
  caseId,
  onProceed,
  onBack,
  isDualLanguage,
}) => {
  const [activeSlot, setActiveSlot] = useState<DocType | null>(null);
  // Documents with missing confidence that the FSO has opened during this session
  const [reviewedDocs, setReviewedDocs] = useState<Set<DocType>>(new Set());
  const [isChecking, setIsChecking] = useState(false);

  // Completed slots with extracted data
  const completedSlots = slots.filter(
    (s) => (s.status === 'done' || s.status === 'not_provided') && (extractedData[s.id] || s.status === 'not_provided')
  );

  // Auto-select first available doc
  useEffect(() => {
    if (!activeSlot) {
      const first = completedSlots.find(
        (s) => s.status === 'done' && extractedData[s.id]
      );
      if (first) setActiveSlot(first.id);
    }
  }, [activeSlot, completedSlots, extractedData]);

  // ── Run cross-check ────────────────────────────────────────────────────

  const runCrossCheck = useCallback(async () => {
    if (!caseId) return;
    setIsChecking(true);
    try {
      const res = await casesApi.crossCheck(caseId);
      setCrossChecks(res.checks as CrossCheckResult[]);
    } catch {
      // silent — cross-check will show stale
    }
    setIsChecking(false);
  }, [caseId, setCrossChecks]);

  useEffect(() => {
    if (Object.keys(extractedData).length >= 2) {
      runCrossCheck();
    }
  }, [extractedData, runCrossCheck]);

  // ── Field edit ─────────────────────────────────────────────────────────

  const handleFieldEdit = async (docType: string, fieldPath: string, newValue: string | null) => {
    if (!caseId) return;

    // Update local state immediately
    setExtractedData((prev) => {
      const copy = { ...prev };
      const data = { ...(copy[docType] || {}) };

      const parts = fieldPath.split('.');
      if (parts.length === 1) {
        data[parts[0]] = newValue;
      } else if (parts.length === 3 && parts[0] === 'children') {
        const idx = parseInt(parts[1]);
        const field = parts[2];
        if (Array.isArray(data.children) && data.children[idx]) {
          data.children = data.children.map((child: any, i: number) =>
            i === idx ? { ...child, [field]: newValue } : child
          );
        }
      }

      copy[docType] = data;
      return copy;
    });

    // Persist to backend
    try {
      await casesApi.updateField(caseId, docType, fieldPath, newValue || '');
    } catch {
      // silent
    }

    // Re-run cross-check after debounce
    setTimeout(() => runCrossCheck(), 500);
  };

  const activeData = activeSlot ? extractedData[activeSlot] : null;
  const activeSlotConfig = activeSlot ? slots.find((s) => s.id === activeSlot) : null;
  const activeImageUrl = activeSlotConfig?.file?.previewUrl;

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-xl hover:bg-slate-200 transition-colors cursor-pointer"
          >
            <ChevronLeft className="w-5 h-5 text-slate-500" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              {isDualLanguage ? 'تصدیق و جائزہ' : 'Review Extractions'}
            </h1>
            <p className="text-sm text-slate-500 mt-0.5">
              {isDualLanguage ? 'نکالے گئے ڈیٹا کی تصدیق اور ترمیم کریں' : 'Verify and edit extracted data'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isChecking && (
            <span className="text-xs text-slate-400 animate-pulse flex items-center gap-1">
              <RefreshCw className="w-3 h-3 animate-spin" />
              Re-validating...
            </span>
          )}
          <button
            onClick={onProceed}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center gap-2 cursor-pointer"
          >
            <span>{isDualLanguage ? 'خلاصہ پر جائیں' : 'Continue to Summary'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Cross-check Pills */}
      {crossChecks.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {crossChecks.map((c, i) => (
            <div
              key={i}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold border flex items-center gap-1.5 ${checkColor(c.status)}`}
            >
              <span>{checkIcon(c.status)}</span>
              <span>{c.label}</span>
              {c.status === 'SIMILAR' && c.similarity != null && (
                <span className="opacity-70">({Math.round(c.similarity * 100)}%)</span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 3-Column Layout */}
      <div className="grid grid-cols-12 gap-5">
        {/* Left: Document Nav */}
        <div className="col-span-3">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
              <h2 className="text-sm font-semibold text-slate-700">
                {isDualLanguage ? 'دستاویزات' : 'Documents'}
              </h2>
            </div>
            <div className="divide-y divide-slate-50">
              {slots.map((slot) => {
                const hasData = extractedData[slot.id] != null;
                const isNotProvided = slot.status === 'not_provided';
                // Input-only slots (FSO-typed, no AI confidence) are never flagged
                const needsReview = !slot.isInputOnly && hasMissingConfidence(extractedData[slot.id]);
                const isReviewed = needsReview && reviewedDocs.has(slot.id);
                const isActive = activeSlot === slot.id;
                return (
                  <button
                    key={slot.id}
                    onClick={() => {
                      setActiveSlot(slot.id);
                      setReviewedDocs((prev) => new Set(prev).add(slot.id));
                    }}
                    title={needsReview ? (isReviewed ? 'Reviewed — missing confidence fields checked' : 'Some extracted fields are missing confidence scores — needs review') : undefined}
                    className={`w-full text-left px-4 py-3 flex items-center gap-3 transition-colors cursor-pointer ${
                      isActive
                        ? isReviewed
                          ? 'bg-sky-50 border-l-3 border-l-indigo-600'
                          : needsReview
                            ? 'bg-rose-50 border-l-3 border-l-indigo-600'
                            : 'bg-indigo-50 border-l-3 border-l-indigo-600'
                        : isReviewed
                          ? 'bg-sky-50 hover:bg-sky-100'
                          : needsReview
                            ? 'bg-rose-50 hover:bg-rose-100'
                            : 'hover:bg-slate-50'
                    }`}
                  >
                    <DocStatusIcon hasData={hasData} isNotProvided={isNotProvided} isError={slot.status === 'error'} />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">{slot.title}</p>
                      {isDualLanguage && (
                        <p className="text-xs text-slate-400 truncate font-urdu" dir="rtl">{slot.urduTitle}</p>
                      )}
                      {needsReview && (
                        isReviewed ? (
                          <p className="text-[10px] font-semibold text-sky-600 flex items-center gap-1 mt-0.5">
                            <CheckCircle2 className="w-3 h-3 shrink-0" />
                            {isDualLanguage ? 'نظر ثانی شدہ' : 'Reviewed'}
                          </p>
                        ) : (
                          <p className="text-[10px] font-semibold text-rose-600 flex items-center gap-1 mt-0.5">
                            <AlertTriangle className="w-3 h-3 shrink-0" />
                            {isDualLanguage ? 'نظر ثانی درکار ہے' : 'Needs Review'}
                          </p>
                        )
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Center: Image */}
        <div className="col-span-4">
          {activeImageUrl ? (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
                <h2 className="text-sm font-semibold text-slate-700">
                  {activeSlotConfig?.title}
                </h2>
              </div>
              <div className="p-2">
                <img src={activeImageUrl} alt="Document" className="w-full rounded-xl" />
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 text-center">
              {activeSlotConfig?.status === 'not_provided' ? (
                <div className="text-slate-400">
                  <AlertTriangle className="w-10 h-10 mx-auto mb-3 opacity-50" />
                  <p className="text-sm font-medium">{isDualLanguage ? 'فراہم نہیں' : 'Not Provided'}</p>
                  <p className="text-xs mt-1">{isDualLanguage ? 'یہ دستاویز فراہم نہیں کی گئی' : 'This document was marked as not provided'}</p>
                </div>
              ) : activeSlotConfig?.isInputOnly && activeData ? (
                <div className="text-left">
                  <h3 className="text-sm font-semibold text-slate-700 mb-2">{activeSlotConfig.title}</h3>
                  <div className="bg-slate-50 rounded-xl p-4 text-sm text-slate-800">
                    {activeSlot === 'address'
                      ? (activeData.full_address as string)
                      : (activeData.label || activeData.education_level) as string}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-slate-400">
                  {isDualLanguage ? 'دیکھنے کے لیے دستاویز منتخب کریں' : 'Select a document to review'}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Right: Extracted Fields */}
        <div className="col-span-5">
          {activeData ? (
            <ExtractedFields
              docType={activeSlot!}
              data={activeData}
              isDualLanguage={isDualLanguage}
              onEdit={handleFieldEdit}
            />
          ) : activeSlotConfig?.status === 'not_provided' ? (
            <div className="bg-white rounded-2xl border border-dashed border-slate-200 shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
                <h2 className="text-sm font-semibold text-slate-700">{activeSlotConfig.title}</h2>
              </div>
              <div className="p-8 text-center">
                <AlertTriangle className="w-10 h-10 text-slate-300 mx-auto mb-3" />
                <p className="text-sm font-medium text-slate-500">
                  {isDualLanguage ? 'دستاویز فراہم نہیں' : 'Document Not Provided'}
                </p>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 text-center text-sm text-slate-400">
              {isDualLanguage ? 'نکالے گئے فیلڈز دیکھنے کے لیے دستاویز منتخب کریں' : 'Select a document to see extracted fields'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ── Extracted Fields Panel ─────────────────────────────────────────────────

function ExtractedFields({
  docType,
  data,
  isDualLanguage,
  onEdit,
}: {
  docType: string;
  data: Record<string, any>;
  isDualLanguage: boolean;
  onEdit: (docType: string, fieldPath: string, value: string | null) => void;
}) {
  const confidence = (data.confidence as Record<string, number>) ?? {};
  // Overall document confidence: average of non-zero field scores
  const fieldScores = Object.values(confidence).filter((v) => typeof v === 'number' && v > 0);
  const docConfidence = fieldScores.length
    ? fieldScores.reduce((a, b) => a + b, 0) / fieldScores.length
    : null;

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">
          {isDualLanguage ? 'نکالے گئے فیلڈز' : 'Extracted Fields'}
        </h2>
        <div className="flex items-center gap-2">
          {docConfidence != null && (
            <span
              className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full border font-bold ${confidenceColor(docConfidence)}`}
              title="Average extraction confidence for this document"
            >
              <span className={`w-1.5 h-1.5 rounded-full ${confidenceDot(docConfidence)}`} />
              {Math.round(docConfidence * 100)}%
            </span>
          )}
          <Edit3 className="w-4 h-4 text-slate-400" />
        </div>
      </div>
      {/* Confidence legend */}
      <div className="px-4 py-2 bg-slate-50/60 border-b border-slate-100 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-slate-400">
        <span className="inline-flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> {isDualLanguage ? 'درست (۹۰٪+)' : 'High (≥90%)'}</span>
        <span className="inline-flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" /> {isDualLanguage ? 'جانچیں (۷۰–۸۹٪)' : 'Check (70–89%)'}</span>
        <span className="inline-flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> {isDualLanguage ? 'غلط ممکن (&lt;۷۰٪)' : 'Likely wrong (<70%)'}</span>
      </div>
      <div className="divide-y divide-slate-50">
        {Object.entries(data)
          .filter(([k]) => !k.startsWith('_') && k !== 'confidence' && k !== 'children')
          .map(([key, value]) => (
            <FieldRow
              key={key}
              docType={docType}
              fieldKey={key}
              value={value}
              confidence={confidence[key]}
              onEdit={onEdit}
            />
          ))}

        {/* B-form children array */}
        {Array.isArray(data.children) && (
          <div className="p-4">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">
              {isDualLanguage ? 'بچوں کی فہرست' : 'Children Listed'}
            </h3>
            <div className="space-y-3">
              {(data.children as Record<string, any>[]).map((child, i) => (
                <div
                  key={i}
                  className={`rounded-xl border p-3 ${
                    child.is_target_child
                      ? 'border-indigo-400 bg-indigo-50'
                      : 'border-slate-200'
                  }`}
                >
                  {child.is_target_child && (
                    <span className="text-xs font-bold text-indigo-600 mb-2 block">
                      ★ {isDualLanguage ? 'مطلوبہ بچہ' : 'Target Child'}
                    </span>
                  )}
                  {Object.entries(child)
                    .filter(([k]) => k !== 'is_target_child')
                    .map(([k, v]) => (
                      <FieldRow
                        key={k}
                        docType={docType}
                        fieldKey={`children.${i}.${k}`}
                        label={`${k} (#${child.serial_number ?? i + 1})`}
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
  );
}

// ── Single Field Row ───────────────────────────────────────────────────────

function FieldRow({
  docType,
  fieldKey,
  label,
  value,
  confidence,
  onEdit,
  compact,
}: {
  docType: string;
  fieldKey: string;
  label?: string;
  value: any;
  confidence?: number;
  onEdit: (docType: string, fieldPath: string, value: string | null) => void;
  compact?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value ?? ''));
  const [error, setError] = useState<string | null>(null);
  const [flashing, setFlashing] = useState(false);
  const displayKey = label ?? fieldKey.split('.').pop() ?? fieldKey;
  const displayVal = value != null ? String(value) : null;
  const rtl = isRTL(displayVal);
  const needsReview = confidence === 0;

  const commit = () => {
    const rule = getFieldRule(docType, fieldKey);
    if (rule && draft !== '' && !rule.test(draft)) {
      setError(rule.message);
      return;
    }
    setError(null);
    setEditing(false);
    if (draft !== String(value ?? '')) {
      onEdit(docType, fieldKey, draft || null);
    }
  };

  return (
    <div className={`px-4 ${compact ? 'py-1.5' : 'py-2.5'} ${confidenceRowAccent(confidence)} ${flashing ? 'animate-review-flash' : ''}`}>
      <div className="flex items-center justify-between gap-2">
        <span className={`text-slate-500 capitalize ${compact ? 'text-xs' : 'text-sm'}`}>
          {displayKey.replace(/_/g, ' ')}
        </span>
        {confidence != null && (
          <span
            className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full border font-bold ${confidenceColor(confidence)}`}
            title={
              confidence === 0
                ? 'Field not found in document'
                : confidence >= 0.9
                ? 'High confidence extraction'
                : confidence >= 0.7
                ? 'Please verify this field'
                : 'Low confidence — please verify and correct'
            }
          >
            <span className={`w-1.5 h-1.5 rounded-full ${confidenceDot(confidence)}`} />
            {confidence === 0 ? 'missing' : `${Math.round(confidence * 100)}%`}
          </span>
        )}
      </div>
      {editing ? (
        <div>
          <input
            autoFocus
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              if (error) setError(null);
            }}
            onBlur={commit}
            onKeyDown={(e) => e.key === 'Enter' && commit()}
            className={`mt-1 w-full px-2 py-1 border rounded-lg text-sm outline-none focus:ring-2 ${
              error
                ? 'border-rose-400 focus:ring-rose-500/20'
                : 'border-indigo-400 focus:ring-indigo-500/20'
            }`}
          />
          {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
        </div>
      ) : (
        <div
          className="flex items-center gap-2 mt-0.5 cursor-pointer group"
          onClick={() => {
            if (needsReview) {
              setFlashing(true);
              setTimeout(() => setFlashing(false), 700);
            }
            setDraft(String(value ?? ''));
            setError(null);
            setEditing(true);
          }}
        >
          {displayVal ? (
            <span className={`${rtl ? 'font-urdu text-sm' : 'text-sm text-slate-900'} ${compact ? 'text-xs' : ''}`}>
              {displayVal}
            </span>
          ) : (
            <span className="text-sm text-slate-300 italic">null</span>
          )}
          <Edit3 className="w-3 h-3 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      )}
    </div>
  );
}

// ── Doc Status Icon ────────────────────────────────────────────────────────

function DocStatusIcon({ hasData, isNotProvided, isError }: { hasData: boolean; isNotProvided: boolean; isError: boolean }) {
  if (isNotProvided) return <AlertTriangle className="w-4 h-4 text-slate-300 shrink-0" />;
  if (hasData) return <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />;
  if (isError) return <XCircle className="w-4 h-4 text-rose-400 shrink-0" />;
  return <div className="w-4 h-4 rounded-full border-2 border-slate-200 shrink-0" />;
}
