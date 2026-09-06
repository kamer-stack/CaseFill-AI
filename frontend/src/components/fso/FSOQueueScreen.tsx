import React, { useState, useEffect } from 'react';
import { AppUser, CaseRecord } from '../../types';
import { casesApi } from '../../lib/api';
import { ReviewedByNote } from '../shared/ReviewedByNote';
import {
  ShieldCheck,
  PlusCircle,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileText,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Flag,
  KeyRound,
  HeartHandshake,
  Trash2,
  Plus,
  Inbox,
} from 'lucide-react';

interface FSOQueueScreenProps {
  user: AppUser;
  onStartIntake: () => void;
  isDualLanguage: boolean;
}

type QueueTab = 'pending' | 'verified' | 'flagged' | 'all';

const statusColor = (s: string) => {
  switch (s) {
    case 'pending_verification': return 'bg-blue-50 text-blue-700 border-blue-200';
    case 'verified': return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    case 'flagged': return 'bg-amber-50 text-amber-700 border-amber-200';
    case 'rejected': return 'bg-rose-50 text-rose-700 border-rose-200';
    case 'draft': return 'bg-slate-50 text-slate-600 border-slate-200';
    case 'unassigned': return 'bg-violet-50 text-violet-700 border-violet-200';
    default: return 'bg-slate-50 text-slate-600 border-slate-200';
  }
};

const statusLabel = (s: string) => {
  switch (s) {
    case 'pending_verification': return 'Pending';
    case 'verified': return 'Verified';
    case 'flagged': return 'Flagged';
    case 'rejected': return 'Rejected';
    case 'draft': return 'Draft';
    case 'unassigned': return 'Unassigned';
    default: return s;
  }
};

export const FSOQueueScreen: React.FC<FSOQueueScreenProps> = ({
  user,
  onStartIntake,
  isDualLanguage,
}) => {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<QueueTab>('pending');
  const [expandedCase, setExpandedCase] = useState<string | null>(null);
  const [caseDetail, setCaseDetail] = useState<Record<string, any> | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Verify/flag state
  const [verifying, setVerifying] = useState<string | null>(null);
  const [flagReason, setFlagReason] = useState('');
  const [showFlagInput, setShowFlagInput] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState('');

  const loadCases = async () => {
    setLoading(true);
    try {
      const res = await casesApi.list({
        role: 'fso',
        fso_id: user.fso_id || user.id,
      });
      setCases(res.cases as CaseRecord[]);
    } catch {
      setCases([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadCases();
  }, [user.fso_id, user.id]);

  const loadCaseDetail = async (caseId: string) => {
    if (expandedCase === caseId) {
      setExpandedCase(null);
      setCaseDetail(null);
      return;
    }
    setLoadingDetail(true);
    setExpandedCase(caseId);
    try {
      const detail = await casesApi.get(caseId);
      setCaseDetail(detail);
    } catch {
      setCaseDetail(null);
    }
    setLoadingDetail(false);
  };

  // Re-fetch the expanded case detail (used after Generate Login / donor / aid-transfer updates)
  const refreshCase = async (caseId: string) => {
    try {
      const detail = await casesApi.get(caseId);
      setCaseDetail(detail);
    } catch {
      // silent
    }
  };

  const handleVerify = async (caseId: string) => {
    setVerifying(caseId);
    try {
      await casesApi.verify(caseId, 'verified', reviewNotes);
      await loadCases();
      setExpandedCase(null);
      setCaseDetail(null);
      setReviewNotes('');
    } catch {
      // silent
    }
    setVerifying(null);
  };

  const handleFlag = async (caseId: string) => {
    if (!flagReason.trim()) return;
    setVerifying(caseId);
    try {
      await casesApi.verify(caseId, 'flagged', reviewNotes, flagReason);
      await loadCases();
      setExpandedCase(null);
      setCaseDetail(null);
      setShowFlagInput(null);
      setFlagReason('');
      setReviewNotes('');
    } catch {
      // silent
    }
    setVerifying(null);
  };

  // Filter cases by tab
  const filteredCases = cases.filter((c) => {
    if (activeTab === 'pending') return c.status === 'pending_verification';
    if (activeTab === 'verified') return c.status === 'verified';
    if (activeTab === 'flagged') return c.status === 'flagged';
    return true;
  });

  const pendingCount = cases.filter((c) => c.status === 'pending_verification').length;
  const verifiedCount = cases.filter((c) => c.status === 'verified').length;
  const flaggedCount = cases.filter((c) => c.status === 'flagged').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {isDualLanguage ? 'تصدیقی قطار' : 'Verification Queue'}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {user.name} &bull; {user.badge || 'FSO Officer'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadCases}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={onStartIntake}
            className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center gap-2 cursor-pointer"
          >
            <PlusCircle className="w-4 h-4" />
            <span>{isDualLanguage ? 'نیا اندراج شروع کریں' : 'Start New Intake'}</span>
          </button>
        </div>
      </div>

      {/* Stats Strip — pending / flagged / verified / all at a glance; doubles as the queue filter */}
      <div className="bg-slate-100 rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-px">
          {([
            {
              key: 'pending' as QueueTab,
              label: isDualLanguage ? 'زیرِ تصدیق' : 'Pending',
              count: pendingCount,
              icon: <Clock className="w-4 h-4" />,
              iconWrap: 'bg-blue-100 text-blue-600',
              value: 'text-blue-600',
              bar: 'bg-blue-500',
            },
            {
              key: 'flagged' as QueueTab,
              label: isDualLanguage ? 'نشان زد' : 'Flagged',
              count: flaggedCount,
              icon: <Flag className="w-4 h-4" />,
              iconWrap: 'bg-amber-100 text-amber-600',
              value: 'text-amber-600',
              bar: 'bg-amber-500',
            },
            {
              key: 'verified' as QueueTab,
              label: isDualLanguage ? 'تصدیق شدہ' : 'Verified',
              count: verifiedCount,
              icon: <CheckCircle2 className="w-4 h-4" />,
              iconWrap: 'bg-emerald-100 text-emerald-600',
              value: 'text-emerald-600',
              bar: 'bg-emerald-500',
            },
            {
              key: 'all' as QueueTab,
              label: isDualLanguage ? 'تمام کیسز' : 'All Cases',
              count: cases.length,
              icon: <ShieldCheck className="w-4 h-4" />,
              iconWrap: 'bg-slate-200 text-slate-600',
              value: 'text-slate-900',
              bar: 'bg-slate-500',
            },
          ]).map((s) => (
            <button
              key={s.key}
              onClick={() => setActiveTab(s.key)}
              className={`relative px-4 py-3.5 flex items-center gap-3 transition-colors cursor-pointer ${
                activeTab === s.key ? 'bg-slate-50' : 'bg-white hover:bg-slate-50'
              }`}
            >
              <span className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${s.iconWrap}`}>
                {s.icon}
              </span>
              <span className="min-w-0 text-left">
                <span className={`text-xl font-black leading-none ${s.value}`}>{s.count}</span>
                <span className="block text-[11px] font-semibold text-slate-500 mt-0.5 truncate">{s.label}</span>
              </span>
              {activeTab === s.key && (
                <span className={`absolute bottom-0 left-0 right-0 h-0.5 ${s.bar}`} />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Case List */}
      {loading ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center">
          <RefreshCw className="w-6 h-6 text-slate-400 animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-400">{isDualLanguage ? 'لوڈ ہو رہا ہے...' : 'Loading cases...'}</p>
        </div>
      ) : filteredCases.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center animate-fade-in-up">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-50 to-slate-100 border border-emerald-100 flex items-center justify-center mx-auto mb-4">
            {activeTab === 'pending' ? (
              <Inbox className="w-8 h-8 text-emerald-500" />
            ) : activeTab === 'flagged' ? (
              <Flag className="w-8 h-8 text-amber-500" />
            ) : activeTab === 'verified' ? (
              <CheckCircle2 className="w-8 h-8 text-emerald-500" />
            ) : (
              <ShieldCheck className="w-8 h-8 text-slate-400" />
            )}
          </div>
          <p className="text-base font-bold text-slate-700">
            {activeTab === 'pending'
              ? (isDualLanguage ? 'کوئی کیس زیرِ تصدیق نہیں' : 'No cases pending')
              : activeTab === 'flagged'
              ? (isDualLanguage ? 'کوئی نشان زد کیس نہیں' : 'No flagged cases')
              : activeTab === 'verified'
              ? (isDualLanguage ? 'ابھی کوئی کیس تصدیق شدہ نہیں' : 'No verified cases yet')
              : (isDualLanguage ? 'کوئی کیس نہیں ملا' : 'No cases found')}
          </p>
          <p className="text-sm text-slate-400 mt-1 max-w-sm mx-auto">
            {activeTab === 'pending'
              ? (isDualLanguage
                  ? 'تمام کیسز کی تصدیق ہو چکی ہے — بہترین کام!'
                  : 'All caught up! Every case in your queue has been reviewed.')
              : (isDualLanguage
                  ? 'اس ٹیب میں ابھی کوئی کیس موجود نہیں ہے'
                  : 'Nothing in this category right now. Cases will appear here automatically.')}
          </p>
          {activeTab === 'pending' && (
            <button
              onClick={onStartIntake}
              className="mt-5 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center gap-2 mx-auto cursor-pointer"
            >
              <PlusCircle className="w-4 h-4" />
              <span>{isDualLanguage ? 'نیا اندراج شروع کریں' : 'Start New Intake'}</span>
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredCases.map((c) => (
            <div
              key={c.id}
              className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden transition-all"
            >
              {/* Case Row */}
              <button
                onClick={() => loadCaseDetail(c.id)}
                className="w-full text-left px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-4 min-w-0">
                  <div className="shrink-0">
                    <StatusIcon status={c.status} />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-sm text-slate-900">{c.case_number}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${statusColor(c.status)}`}>
                        {statusLabel(c.status)}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {c.submission_source === 'family_self_service' ? 'Family Self-Service' : 'FSO Manual'} &bull;{' '}
                      {new Date(c.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {c.child_crc && (
                    <span className="text-xs font-mono text-slate-400 hidden sm:inline">CRC: {c.child_crc}</span>
                  )}
                  {c.average_confidence != null && (
                    <span
                      className={`inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-full border font-bold ${
                        c.average_confidence >= 0.9 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                        c.average_confidence >= 0.7 ? 'bg-amber-50 text-amber-700 border-amber-200' :
                        'bg-rose-50 text-rose-700 border-rose-200'
                      }`}
                      title="Average AI extraction confidence"
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        c.average_confidence >= 0.9 ? 'bg-emerald-500' :
                        c.average_confidence >= 0.7 ? 'bg-amber-500' :
                        'bg-rose-500'
                      }`} />
                      {Math.round(c.average_confidence * 100)}%
                    </span>
                  )}
                  {expandedCase === c.id ? (
                    <ChevronUp className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  )}
                </div>
              </button>

              {/* Expanded Detail */}
              {expandedCase === c.id && (
                <div className="border-t border-slate-100 px-5 py-4 bg-slate-50/50">
                  {loadingDetail ? (
                    <div className="flex items-center justify-center py-6">
                      <RefreshCw className="w-5 h-5 text-slate-400 animate-spin" />
                    </div>
                  ) : caseDetail ? (
                    <CaseDetailView
                      detail={caseDetail}
                      caseRecord={c}
                      isDualLanguage={isDualLanguage}
                      verifying={verifying === c.id}
                      showFlagInput={showFlagInput === c.id}
                      flagReason={flagReason}
                      setFlagReason={setFlagReason}
                      reviewNotes={reviewNotes}
                      setReviewNotes={setReviewNotes}
                      onVerify={() => handleVerify(c.id)}
                      onFlag={() => handleFlag(c.id)}
                      onShowFlag={() => setShowFlagInput(c.id)}
                      onCancelFlag={() => { setShowFlagInput(null); setFlagReason(''); }}
                      onRefresh={() => refreshCase(c.id)}
                    />
                  ) : (
                    <p className="text-sm text-slate-400 text-center py-4">Failed to load case details</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ── Case Detail View ───────────────────────────────────────────────────────

function CaseDetailView({
  detail,
  caseRecord,
  isDualLanguage,
  verifying,
  showFlagInput,
  flagReason,
  setFlagReason,
  reviewNotes,
  setReviewNotes,
  onVerify,
  onFlag,
  onShowFlag,
  onCancelFlag,
  onRefresh,
}: {
  detail: Record<string, any>;
  caseRecord: CaseRecord;
  isDualLanguage: boolean;
  verifying: boolean;
  showFlagInput: boolean;
  flagReason: string;
  setFlagReason: (v: string) => void;
  reviewNotes: string;
  setReviewNotes: (v: string) => void;
  onVerify: () => void;
  onFlag: () => void;
  onShowFlag: () => void;
  onCancelFlag: () => void;
  onRefresh: () => void;
}) {
  // ── Child login / donor / aid-transfer state (verified cases) ──
  const [genBusy, setGenBusy] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [donorBusy, setDonorBusy] = useState(false);
  const [transferDate, setTransferDate] = useState('');
  const [transferAmount, setTransferAmount] = useState('');
  const [transferBusy, setTransferBusy] = useState(false);
  const [transferError, setTransferError] = useState<string | null>(null);

  const documents = Object.values(detail.documents || {});
  const compiled = detail.compiled_json ? JSON.parse(detail.compiled_json) : null;
  const donorArranged = !!detail.donor_arranged;
  const aidEntries: { date: string; amount: number; recorded_by?: string }[] =
    Array.isArray(detail.aid_transfer_log) ? detail.aid_transfer_log : [];

  const handleGenerateLogin = async () => {
    setGenBusy(true);
    setGenError(null);
    try {
      await casesApi.generateLogin(caseRecord.id);
      onRefresh();
    } catch (e: any) {
      setGenError(e.message || 'Failed to generate login');
    }
    setGenBusy(false);
  };

  const handleToggleDonor = async (next: boolean) => {
    setDonorBusy(true);
    try {
      await casesApi.setDonorStatus(caseRecord.id, next);
      onRefresh();
    } catch (e: any) {
      alert(e.message || 'Failed to update donor status');
    }
    setDonorBusy(false);
  };

  const handleAddTransfer = async () => {
    if (!transferDate || !transferAmount) return;
    setTransferBusy(true);
    setTransferError(null);
    try {
      await casesApi.addAidTransfer(caseRecord.id, {
        date: transferDate,
        amount: Number(transferAmount),
      });
      setTransferDate('');
      setTransferAmount('');
      onRefresh();
    } catch (e: any) {
      setTransferError(e.message || 'Failed to add transfer entry');
    }
    setTransferBusy(false);
  };

  const handleRemoveTransfer = async (index: number) => {
    try {
      await casesApi.removeAidTransfer(caseRecord.id, index);
      onRefresh();
    } catch {
      // silent
    }
  };

  return (
    <div className="space-y-4">
      {/* Documents Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {documents.map((doc: any) => (
          <div key={doc.doc_type} className="bg-white rounded-xl border border-slate-200 p-3 text-center">
            <p className="text-xs font-semibold text-slate-700 capitalize mb-1">
              {doc.doc_type.replace(/_/g, ' ')}
            </p>
            {doc.imageUrl ? (
              <img
                src={doc.imageUrl}
                alt={doc.doc_type}
                className="w-full h-20 object-cover rounded-lg border border-slate-100"
              />
            ) : (
              <div className="w-full h-20 bg-slate-100 rounded-lg flex items-center justify-center">
                <FileText className="w-5 h-5 text-slate-300" />
              </div>
            )}
            <p className="text-[10px] text-slate-400 mt-1">{doc.status}</p>
          </div>
        ))}
      </div>

      {/* Compiled info summary */}
      {compiled && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          {compiled.child_name && (
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <span className="text-slate-400 block">Child Name</span>
              <span className="font-semibold text-slate-900">{compiled.child_name}</span>
            </div>
          )}
          {compiled.father_name && (
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <span className="text-slate-400 block">Father Name</span>
              <span className="font-semibold text-slate-900">{compiled.father_name}</span>
            </div>
          )}
          {compiled.mother_name && (
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <span className="text-slate-400 block">Mother Name</span>
              <span className="font-semibold text-slate-900">{compiled.mother_name}</span>
            </div>
          )}
          {compiled.residential_address && (
            <div className="bg-white rounded-xl border border-slate-200 p-3">
              <span className="text-slate-400 block">Address</span>
              <span className="font-semibold text-slate-900">{compiled.residential_address}</span>
            </div>
          )}
        </div>
      )}

      {/* Attribution */}
      {(caseRecord.submitted_by_fso_name || caseRecord.assigned_fso_name) && (
        <div className="text-[11px] text-slate-400 flex flex-wrap gap-x-4">
          {caseRecord.submitted_by_fso_name && (
            <span>Submitted by FSO: <strong className="text-slate-600">{caseRecord.submitted_by_fso_name}</strong></span>
          )}
          {caseRecord.assigned_fso_name && (
            <span>Assigned to: <strong className="text-slate-600">{caseRecord.assigned_fso_name}</strong></span>
          )}
        </div>
      )}

      {/* Reviewed-by note on verified cases */}
      {caseRecord.status === 'verified' && (
        <ReviewedByNote
          name={detail.verified_by_fso_name || caseRecord.verified_by_fso_name || caseRecord.assigned_fso_name}
          date={caseRecord.verified_at || detail.verified_at}
          isDualLanguage={isDualLanguage}
        />
      )}

      {/* ── Verified-case controls: child login, donor status, aid transfers ── */}
      {caseRecord.status === 'verified' && (
        <div className="space-y-4 pt-1">
          {/* Child Login */}
          <div className="bg-white rounded-xl border border-indigo-200 p-4 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-indigo-700 flex items-center gap-1.5">
              <KeyRound className="w-3.5 h-3.5" />
              {isDualLanguage ? 'بچے کا لاگ ان (صرف مطالعہ)' : 'Child Login (Read-only)'}
            </h4>
            {detail.child_username ? (
              <div className="space-y-2">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <div className="bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-2">
                    <span className="text-[10px] font-bold uppercase text-indigo-400 block">Username (B-Form No.)</span>
                    <span className="text-sm font-mono font-bold text-slate-900">{detail.child_username}</span>
                  </div>
                  <div className="bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-2">
                    <span className="text-[10px] font-bold uppercase text-indigo-400 block">Password</span>
                    <span className="text-sm font-mono font-bold text-slate-900">{detail.child_password}</span>
                  </div>
                </div>
                <p className="text-[11px] text-slate-400">
                  {isDualLanguage
                    ? 'یہ اسناد بچے کی پروفائل اسکرین پر بھی دکھائی جاتی ہیں۔ بچے کا لاگ ان صرف مطالعے کے لیے ہے۔'
                    : "These credentials are shown on the child's profile screen. The child login is strictly read-only."}
                </p>
                <button
                  onClick={handleGenerateLogin}
                  disabled={genBusy}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-bold flex items-center gap-1 cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw className={`w-3 h-3 ${genBusy ? 'animate-spin' : ''}`} />
                  <span>Reset password</span>
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-slate-500">
                  {isDualLanguage
                    ? 'تصدیق کے بعد بچے کے لیے صرف مطالعہ والا لاگ ان بنائیں (یوزر نیم = ب فارم نمبر)'
                    : 'Create the read-only login for the child (username = B-Form registration number).'}
                </p>
                <button
                  onClick={handleGenerateLogin}
                  disabled={genBusy}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-sm disabled:opacity-50 transition-all flex items-center gap-2 cursor-pointer"
                >
                  {genBusy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <KeyRound className="w-3.5 h-3.5" />}
                  <span>{isDualLanguage ? 'لاگ ان بنائیں' : 'Generate Login'}</span>
                </button>
              </div>
            )}
            {genError && (
              <p className="text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">{genError}</p>
            )}
          </div>

          {/* Donor Status + Aid Transfers */}
          <div className="bg-white rounded-xl border border-emerald-200 p-4 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-700 flex items-center gap-1.5">
              <HeartHandshake className="w-3.5 h-3.5" />
              {isDualLanguage ? 'عطیہ دہندہ اور امدادی منتقلی' : 'Donor Status & Aid Transfers'}
            </h4>

            {/* Donor toggle */}
            <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
              <span className="text-xs font-semibold text-slate-700">
                {isDualLanguage ? 'عطیہ دہندہ مقرر ہے؟' : 'Donor Arranged?'}
              </span>
              <div className="flex items-center gap-1">
                {[true, false].map((val) => (
                  <button
                    key={String(val)}
                    onClick={() => handleToggleDonor(val)}
                    disabled={donorBusy || donorArranged === val}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer disabled:cursor-default ${
                      donorArranged === val
                        ? val
                          ? 'bg-emerald-600 text-white shadow-sm'
                          : 'bg-slate-600 text-white shadow-sm'
                        : 'bg-white border border-slate-300 text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {val ? (isDualLanguage ? 'جی ہاں' : 'Yes') : (isDualLanguage ? 'نہیں' : 'No')}
                  </button>
                ))}
              </div>
            </div>

            {/* Aid transfer log */}
            <div className="space-y-2">
              <span className="text-xs font-semibold text-slate-700 block">
                {isDualLanguage ? 'امدادی منتقلی کا ریکارڈ' : 'Aid Transfer Log'}
              </span>
              {aidEntries.length > 0 ? (
                <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden">
                  <div className="grid grid-cols-[1fr_1fr_auto] bg-slate-50 px-3 py-1.5 text-[10px] font-bold uppercase text-slate-400">
                    <span>{isDualLanguage ? 'تاریخ' : 'Date'}</span>
                    <span>{isDualLanguage ? 'رقم' : 'Amount (PKR)'}</span>
                    <span />
                  </div>
                  {aidEntries.map((t, i) => (
                    <div key={i} className="grid grid-cols-[1fr_1fr_auto] items-center px-3 py-1.5 text-xs bg-white">
                      <span className="text-slate-700">{t.date}</span>
                      <span className="font-bold text-slate-900">{t.amount.toLocaleString()}</span>
                      <button
                        onClick={() => handleRemoveTransfer(i)}
                        className="p-1 rounded text-slate-300 hover:text-rose-500 cursor-pointer"
                        title="Remove entry"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic">
                  {isDualLanguage ? 'ابھی کوئی منتقلی درج نہیں ہوئی' : 'No transfers recorded yet.'}
                </p>
              )}

              {/* Add entry */}
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  type="date"
                  value={transferDate}
                  onChange={(e) => setTransferDate(e.target.value)}
                  className="px-3 py-2 border border-slate-300 rounded-xl text-xs focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 outline-none"
                />
                <input
                  type="number"
                  min={1}
                  value={transferAmount}
                  onChange={(e) => setTransferAmount(e.target.value)}
                  placeholder="Amount (PKR)"
                  className="px-3 py-2 border border-slate-300 rounded-xl text-xs focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 outline-none"
                />
                <button
                  onClick={handleAddTransfer}
                  disabled={transferBusy || !transferDate || !transferAmount}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow-sm disabled:opacity-40 transition-all flex items-center gap-1.5 cursor-pointer whitespace-nowrap"
                >
                  {transferBusy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                  <span>{isDualLanguage ? 'شامل کریں' : 'Add Entry'}</span>
                </button>
              </div>
              {transferError && (
                <p className="text-xs text-rose-600">{transferError}</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Review Notes */}
      <div>
        <label className="block text-xs font-semibold text-slate-700 mb-1">
          {isDualLanguage ? 'جائزہ نوٹس' : 'Review Notes'} (optional)
        </label>
        <input
          type="text"
          value={reviewNotes}
          onChange={(e) => setReviewNotes(e.target.value)}
          placeholder="e.g. All documents verified, home visit scheduled..."
          className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 outline-none"
        />
      </div>

      {/* Actions */}
      {caseRecord.status === 'pending_verification' && (
        <div className="flex items-center gap-3 pt-2 border-t border-slate-200">
          {!showFlagInput ? (
            <>
              <button
                onClick={onVerify}
                disabled={verifying}
                className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow-sm disabled:opacity-50 transition-all flex items-center gap-2 cursor-pointer"
              >
                {verifying ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                )}
                <span>{isDualLanguage ? 'تصدیق کریں' : 'Verify & Approve'}</span>
              </button>
              <button
                onClick={onShowFlag}
                className="px-5 py-2.5 bg-amber-500 hover:bg-amber-600 text-white font-bold text-xs rounded-xl shadow-sm transition-all flex items-center gap-2 cursor-pointer"
              >
                <Flag className="w-3.5 h-3.5" />
                <span>{isDualLanguage ? 'فلگ کریں' : 'Flag for Review'}</span>
              </button>
            </>
          ) : (
            <div className="w-full space-y-2">
              <input
                type="text"
                value={flagReason}
                onChange={(e) => setFlagReason(e.target.value)}
                placeholder="Reason for flagging (required)..."
                className="w-full px-3 py-2 bg-white border border-amber-300 rounded-xl text-xs focus:ring-2 focus:ring-amber-300 outline-none"
              />
              <div className="flex gap-2">
                <button
                  onClick={onFlag}
                  disabled={verifying || !flagReason.trim()}
                  className="px-5 py-2 bg-amber-500 hover:bg-amber-600 text-white font-bold text-xs rounded-xl shadow-sm disabled:opacity-50 transition-all flex items-center gap-2 cursor-pointer"
                >
                  {verifying ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Flag className="w-3.5 h-3.5" />}
                  <span>Confirm Flag</span>
                </button>
                <button
                  onClick={onCancelFlag}
                  className="px-3 py-2 border border-slate-300 text-slate-600 text-xs rounded-xl hover:bg-slate-100 cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Already verified/flagged info */}
      {caseRecord.status === 'verified' && caseRecord.fso_review_notes && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-xs text-emerald-800">
          <strong>Review Notes:</strong> {caseRecord.fso_review_notes}
        </div>
      )}
      {caseRecord.status === 'flagged' && caseRecord.flag_reason && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800">
          <strong>Flag Reason:</strong> {caseRecord.flag_reason}
        </div>
      )}
    </div>
  );
}

// ── Status Icon ────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'pending_verification': return <Clock className="w-5 h-5 text-blue-500" />;
    case 'verified': return <CheckCircle2 className="w-5 h-5 text-emerald-500" />;
    case 'flagged': return <AlertTriangle className="w-5 h-5 text-amber-500" />;
    case 'rejected': return <XCircle className="w-5 h-5 text-rose-500" />;
    default: return <FileText className="w-5 h-5 text-slate-400" />;
  }
}
