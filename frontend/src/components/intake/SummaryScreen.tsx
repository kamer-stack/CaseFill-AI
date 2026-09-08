import React, { useState } from 'react';
import { AppUser, CrossCheckResult, INITIAL_DOCUMENT_SLOTS } from '../../types';
import { casesApi } from '../../lib/api';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ChevronLeft,
  Send,
  RotateCcw,
  Clock,
} from 'lucide-react';

interface SummaryScreenProps {
  extractedData: Record<string, any>;
  crossChecks: CrossCheckResult[];
  caseId: string;
  user: AppUser;
  elapsedSeconds: number;
  onComplete: () => void;
  onBack: () => void;
  isDualLanguage: boolean;
}

// Re-use helpers
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

const confidenceDot = (c: number) => {
  if (c >= 0.9) return 'bg-emerald-500';
  if (c >= 0.7) return 'bg-amber-500';
  if (c === 0) return 'bg-slate-300';
  return 'bg-rose-500';
};

const formatTime = (secs: number) => {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

export const SummaryScreen: React.FC<SummaryScreenProps> = ({
  extractedData,
  crossChecks,
  caseId,
  user,
  elapsedSeconds,
  onComplete,
  onBack,
  isDualLanguage,
}) => {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<{ caseNumber: string; status: string; routing: any } | null>(null);
  const [acknowledgment, setAcknowledgment] = useState('');

  const flagsCount = crossChecks.filter(
    (c) => c.status === 'MISMATCH' || c.status === 'SIMILAR' || c.status === 'NEEDS_REVIEW' || c.status === 'DIFFERENT_SCRIPT'
  ).length;
  const isClean = flagsCount === 0;

  const slotDefs = INITIAL_DOCUMENT_SLOTS;

  // ── Submit ─────────────────────────────────────────────────────────────

  const handleSubmit = async () => {
    if (!isClean && !acknowledgment.trim()) return;
    setSubmitting(true);
    setError(null);

    try {
      const res = await casesApi.submit(caseId, acknowledgment);
      setSubmitted({
        caseNumber: res.case_number,
        status: res.status,
        routing: res.routing,
      });
    } catch (err: any) {
      setError(err.message || 'Submission failed');
    }
    setSubmitting(false);
  };

  // ── Already Submitted ──────────────────────────────────────────────────

  if (submitted) {
    return (
      <div className="max-w-3xl mx-auto py-16 text-center">
        <div className="bg-white rounded-3xl border border-emerald-200 shadow-xl p-12">
          <CheckCircle2 className="w-16 h-16 text-emerald-500 mx-auto mb-6" />
          <h1 className="text-2xl font-bold text-slate-900 mb-2">
            {isDualLanguage ? 'کیس جمع ہو گیا' : 'Case Submitted'}
          </h1>
          <p className="text-slate-500 mb-4">
            {isDualLanguage ? 'کیس نمبر' : 'Case Number'}:{' '}
            <span className="font-mono font-bold text-emerald-600">{submitted.caseNumber}</span>
          </p>

          {submitted.routing && (
            <div className="bg-slate-50 rounded-xl p-4 mb-4 text-sm text-slate-600 inline-block">
              <p>
                <strong>{isDualLanguage ? 'علاقہ' : 'Region'}:</strong> {submitted.routing.regionName || 'Unassigned Queue'}
              </p>
              {submitted.routing.fsoName && (
                <p>
                  <strong>{isDualLanguage ? 'مختص FSO' : 'Assigned FSO'}:</strong> {submitted.routing.fsoName}
                </p>
              )}
              <p className="text-xs text-slate-400 mt-1">
                {isDualLanguage ? 'حالت' : 'Status'}: {submitted.status}
              </p>
            </div>
          )}

          {!isClean && (
            <p className="text-sm text-amber-700 bg-amber-50 rounded-xl px-4 py-2 inline-block mb-6">
              {isDualLanguage
                ? `${flagsCount} حل نہ ہونے والے flags کے ساتھ جمع کیا گیا`
                : `Submitted with ${flagsCount} unresolved flag${flagsCount > 1 ? 's' : ''}`}
            </p>
          )}

          <div className="mt-4">
            <button
              onClick={onComplete}
              className="px-5 py-2.5 border border-slate-300 text-slate-600 rounded-xl hover:bg-slate-50 transition-colors text-sm font-semibold flex items-center gap-2 mx-auto cursor-pointer"
            >
              <RotateCcw className="w-4 h-4" />
              {isDualLanguage ? 'نیا کیس شروع کریں' : 'Start New Case'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Pre-submission Summary ─────────────────────────────────────────────

  return (
    <div className="max-w-5xl mx-auto space-y-6">
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
              {isDualLanguage ? 'کیس خلاصہ' : 'Case Summary'}
            </h1>
            <p className="text-sm text-slate-500 mt-0.5">
              {isDualLanguage ? 'جمع کرانے سے پہلے تمام ڈیٹا کا جائزہ لیں' : 'Review all data before submission'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Clock className="w-3.5 h-3.5" />
          <span>{formatTime(elapsedSeconds)}</span>
        </div>
      </div>

      {/* Status Banner */}
      <div
        className={`rounded-2xl p-4 flex items-center gap-3 ${
          isClean
            ? 'bg-emerald-50 border border-emerald-200'
            : 'bg-amber-50 border border-amber-200'
        }`}
      >
        {isClean ? (
          <>
            <CheckCircle2 className="w-6 h-6 text-emerald-600" />
            <div>
              <p className="font-bold text-emerald-800">
                {isDualLanguage ? 'جمع کرانے کے لیے تیار' : 'Ready to submit'}
              </p>
              <p className="text-sm text-emerald-600">
                {isDualLanguage ? 'تمام کراس چیکس پاس ہو گئے' : 'All cross-checks passed'}
              </p>
            </div>
          </>
        ) : (
          <>
            <AlertTriangle className="w-6 h-6 text-amber-600" />
            <div>
              <p className="font-bold text-amber-800">
                {flagsCount} item{flagsCount > 1 ? 's' : ''} need{flagsCount === 1 ? 's' : ''} review
              </p>
              <p className="text-sm text-amber-600">
                {isDualLanguage ? 'آپ اعتراف کے ساتھ جمع kara سکتے ہیں' : 'You can still submit with an acknowledgment'}
              </p>
            </div>
          </>
        )}
      </div>

      {/* Cross-check Results */}
      {crossChecks.length > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
            <h2 className="text-sm font-semibold text-slate-700">
              {isDualLanguage ? 'کراس دستاویز توثیق' : 'Cross-Document Validation'}
            </h2>
          </div>
          <div className="divide-y divide-slate-50">
            {crossChecks.map((c, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between gap-4">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-lg">{checkIcon(c.status)}</span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900">{c.label}</p>
                    {c.detail && <p className="text-xs text-slate-400 truncate">{c.detail}</p>}
                  </div>
                </div>
                <span className={`text-xs px-2.5 py-1 rounded-full border font-semibold shrink-0 ${checkColor(c.status)}`}>
                  {c.status === 'SIMILAR' && c.similarity != null
                    ? `SIMILAR (${Math.round(c.similarity * 100)}%)`
                    : c.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Document Summaries */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {slotDefs.map((slotDef) => {
          const data = extractedData[slotDef.id];
          const slot = slotDef;

          if (slot.status === 'not_provided' && !data) {
            return (
              <div key={slotDef.id} className="bg-slate-50 rounded-2xl border border-dashed border-slate-200 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-slate-300" />
                  <h3 className="text-sm font-semibold text-slate-500">{slotDef.title}</h3>
                </div>
                <p className="text-xs text-slate-400 italic">{isDualLanguage ? 'فراہم نہیں' : 'Not provided'}</p>
              </div>
            );
          }

          if (!data) return null;

          const conf = (data.confidence as Record<string, number>) ?? {};

          return (
            <div key={slotDef.id} className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4">
              <h3 className="text-sm font-semibold text-slate-900 mb-3">
                {slotDef.title}
                {isDualLanguage && (
                  <span className="text-xs font-urdu text-slate-400 ml-2" dir="rtl">{slotDef.urduTitle}</span>
                )}
              </h3>
              <div className="space-y-1.5">
                {Object.entries(data)
                  .filter(([k]) => !k.startsWith('_') && k !== 'confidence' && k !== 'children')
                  .map(([key, val]) => (
                    <div key={key} className="flex items-center justify-between gap-2">
                      <span className="text-xs text-slate-500 capitalize">{key.replace(/_/g, ' ')}</span>
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-xs text-slate-900 truncate">
                          {val != null ? String(val) : '—'}
                        </span>
                        {conf[key] != null && (
                          <span className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full border font-bold ${confidenceColor(conf[key])}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${confidenceDot(conf[key])}`} />
                            {conf[key] === 0 ? '—' : `${Math.round(conf[key] * 100)}%`}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                {/* B-form children summary */}
                {Array.isArray(data.children) && (
                  <div className="mt-2 pt-2 border-t border-slate-100">
                    <span className="text-xs text-slate-500">
                      {(data.children as any[]).length} children listed
                      {(data.children as any[]).some((c: any) => c.is_target_child) && (
                        <span className="text-indigo-600 font-medium ml-1">
                          (target: #{(data.children as any[]).find((c: any) => c.is_target_child)?.serial_number})
                        </span>
                      )}
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Acknowledgment (required when flags exist) */}
      {!isClean && (
        <div className="bg-amber-50 rounded-2xl border border-amber-200 p-5">
          <label className="block text-sm font-bold text-amber-800 mb-2">
            {isDualLanguage ? 'اعتراف درکار ہے' : 'Acknowledgment required'}
          </label>
          <p className="text-xs text-amber-600 mb-3">
            There {flagsCount === 1 ? 'is' : 'are'} {flagsCount} unresolved flag{flagsCount > 1 ? 's' : ''}. Please provide a brief reason before submitting.
          </p>
          <textarea
            value={acknowledgment}
            onChange={(e) => setAcknowledgment(e.target.value)}
            placeholder="e.g. CNIC number discrepancy confirmed with family via phone call..."
            rows={3}
            className="w-full px-3 py-2 border border-amber-300 rounded-xl text-sm bg-white focus:ring-2 focus:ring-amber-300 focus:border-amber-400 outline-none resize-none"
          />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-rose-50 rounded-2xl border border-rose-200 p-4 text-sm text-rose-700 flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-3">
        <button
          onClick={onBack}
          className="px-5 py-2.5 border border-slate-300 text-slate-600 rounded-xl hover:bg-slate-50 transition-colors font-semibold text-sm cursor-pointer"
        >
          {isDualLanguage ? '← جائزہ پر واپس' : '← Back to Review'}
        </button>
        <button
          onClick={handleSubmit}
          disabled={submitting || (!isClean && !acknowledgment.trim())}
          className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm rounded-xl shadow-md disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-2 cursor-pointer"
        >
          {submitting ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              {isDualLanguage ? 'جمع ہو رہا ہے...' : 'Submitting...'}
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              {isDualLanguage ? 'کیس جمع کرائیں' : 'Submit Case'}
            </>
          )}
        </button>
      </div>
    </div>
  );
};
