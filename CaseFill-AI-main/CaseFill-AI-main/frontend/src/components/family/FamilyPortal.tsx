import React, { useState, useEffect } from 'react';
import { AppUser } from '../../types';
import { casesApi } from '../../lib/api';
import { ReviewedByNote } from '../shared/ReviewedByNote';
import {
  Clock,
  CheckCircle2,
  AlertTriangle,
  FileText,
  RefreshCw,
  MapPin,
  Phone,
  ShieldCheck,
  KeyRound,
  HeartHandshake,
} from 'lucide-react';

interface FamilyPortalProps {
  user: AppUser;
  isDualLanguage: boolean;
}

export const FamilyPortal: React.FC<FamilyPortalProps> = ({ user, isDualLanguage }) => {
  const [cases, setCases] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [caseDetail, setCaseDetail] = useState<Record<string, any> | null>(null);

  const loadCases = async () => {
    setLoading(true);
    try {
      const res = await casesApi.list({ role: 'family', family_id: user.id });
      setCases(res.cases || []);
      // Load detail for first case
      if (res.cases?.length > 0) {
        try {
          const detail = await casesApi.get(res.cases[0].id);
          setCaseDetail(detail);
        } catch {
          // silent
        }
      }
    } catch {
      setCases([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadCases();
  }, [user.id]);

  const latestCase = cases[0] || null;

  // ── Loading ────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto py-16 text-center">
        <RefreshCw className="w-8 h-8 text-slate-400 animate-spin mx-auto mb-4" />
        <p className="text-sm text-slate-500">{isDualLanguage ? 'لوڈ ہو رہا ہے...' : 'Loading your case...'}</p>
      </div>
    );
  }

  // ── No Case ────────────────────────────────────────────────────────────

  if (!latestCase) {
    return (
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Profile Card */}
        <ProfileCard user={user} isDualLanguage={isDualLanguage} />

        <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-8 text-center">
          <div className="w-16 h-16 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-4">
            <FileText className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">
            {isDualLanguage ? 'کوئی کیس نہیں ملا' : 'No Case Found'}
          </h2>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            {isDualLanguage
              ? 'ابھی تک کوئی کیس درج نہیں ہوا۔ براہ کرم اپنے قریب ترین الخدمت فیلڈ آفیسر سے ملیں جو آپ کے دستاویزات اپلوڈ کریں گے۔'
              : 'No case has been registered yet. Please visit your nearest Alkhidmat Field Support Officer who will upload your documents and initiate the verification process.'}
          </p>
          <div className="mt-6 bg-slate-50 rounded-2xl p-4 text-xs text-slate-500 max-w-md mx-auto">
            <p className="font-semibold text-slate-700 mb-2">
              {isDualLanguage ? 'اگلے اقدامات' : 'Next Steps:'}
            </p>
            <ul className="text-left space-y-1.5">
              <li className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">1</span>
                <span>{isDualLanguage ? 'اپنے علاقے کے الخدمت دفتر سے رابطہ کریں' : 'Contact your local Alkhidmat Foundation office'}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">2</span>
                <span>{isDualLanguage ? '8 دستاویزات لے کر آئیں' : 'Bring the 8 required documents (B-Form, CNIC, Death Certificate, etc.)'}</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">3</span>
                <span>{isDualLanguage ? 'FSO آپ کا کیس درج کرے گا' : 'The FSO will register your case and you can track it here'}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  // ── Has Case ───────────────────────────────────────────────────────────

  const compiled = caseDetail?.compiled_json ? JSON.parse(caseDetail.compiled_json) : null;
  const documents = Object.values(caseDetail?.documents || {});
  const donorArranged = !!(caseDetail?.donor_arranged ?? latestCase.donor_arranged);
  const aidLog: { date: string; amount: number }[] = Array.isArray(caseDetail?.aid_transfer_log)
    ? caseDetail.aid_transfer_log
    : [];
  const isPending = latestCase.status === 'pending_verification' || latestCase.status === 'unassigned' || latestCase.status === 'draft';
  const isVerified = latestCase.status === 'verified';
  const isFlagged = latestCase.status === 'flagged';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Profile Card */}
      <ProfileCard user={user} isDualLanguage={isDualLanguage} />
  
      {/* Login credentials (generated by the FSO after verification — same case record) */}
      {caseDetail?.child_username && (
        <div className="bg-white rounded-3xl border-2 border-indigo-200 shadow-sm p-5">
          <h3 className="text-sm font-bold text-indigo-700 flex items-center gap-2 mb-3">
            <KeyRound className="w-4 h-4" />
            {isDualLanguage ? 'آپ کے لاگ ان کی اسناد' : 'Your Login Credentials'}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="bg-indigo-50 border border-indigo-200 rounded-xl px-4 py-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 block">
                {isDualLanguage ? 'یوزر نیم (ب فارم نمبر)' : 'Username (B-Form No.)'}
              </span>
              <span className="text-sm font-mono font-bold text-slate-900">{caseDetail.child_username}</span>
            </div>
            <div className="bg-indigo-50 border border-indigo-200 rounded-xl px-4 py-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 block">
                {isDualLanguage ? 'پاس ورڈ' : 'Password'}
              </span>
              <span className="text-sm font-mono font-bold text-slate-900">{caseDetail.child_password}</span>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 mt-3">
            {isDualLanguage
              ? 'یہ اسناد آپ کے کیس ریکارڈ سے لی گئی ہیں۔ براہ کرم محفوظ رکھیں۔'
              : 'These credentials come from your case record. Please keep them safe.'}
          </p>
        </div>
      )}
  
      {/* Success alert after verification */}
      {isVerified && (
        <div className="bg-emerald-50 border-2 border-emerald-300 text-emerald-950 rounded-2xl p-4 shadow-sm flex items-center gap-3">
          <CheckCircle2 className="w-6 h-6 text-emerald-600 shrink-0" />
          <div>
            <p className="text-sm font-bold">
              {isDualLanguage ? 'تصدیق شدہ اور منظور شدہ' : 'Verified & Approved'}
            </p>
            <p className="text-xs text-emerald-700">
              {isDualLanguage ? 'آپ کا کیس تصدیق ہو گیا ہے' : 'Your case has been verified. Educational stipend eligibility confirmed.'}
            </p>
          </div>
        </div>
      )}

      {/* Reviewed-by note on the verified case (read from the same case record) */}
      {isVerified && (
        <ReviewedByNote
          name={caseDetail?.verified_by_fso_name || latestCase.verified_by_fso_name || latestCase.assigned_fso_name}
          date={latestCase.verified_at || caseDetail?.verified_at}
          isDualLanguage={isDualLanguage}
        />
      )}

      {/* Status Card */}
      <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              {isDualLanguage ? 'درخواست نمبر' : 'Application Number'}
            </span>
            <h2 className="text-2xl font-black text-slate-900 tracking-tight mt-0.5">
              {latestCase.case_number}
            </h2>
          </div>
          <div className="flex items-center gap-3">
            <StatusPill status={latestCase.status} isDualLanguage={isDualLanguage} />
            <button
              onClick={loadCases}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-500 transition-colors cursor-pointer"
              title={isDualLanguage ? 'تازہ کاری' : 'Refresh'}
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Status-specific content */}
        <div className="px-6 py-5 space-y-4">
          {isPending && (
            <div className="p-4 rounded-2xl bg-blue-50 border border-blue-200 text-sm">
              <div className="font-bold flex items-center gap-2 mb-1 text-blue-900">
                <Clock className="w-4 h-4 text-blue-600" />
                <span>{isDualLanguage ? 'اگلا قدم: فیلڈ تصدیقی دورہ' : 'Next Step: Field Verification Visit'}</span>
              </div>
              <p className="text-blue-700 text-xs leading-relaxed">
                {isDualLanguage
                  ? 'آپ کی درخواست موصول ہو گئی ہے اور آپ کے علاقے کے فیلڈ سپورٹ آفیسر کو بھیج دی گئی ہے۔ وہ اپلوڈ کردہ دستاویزات کا جائزہ لیں گے۔'
                  : 'Your application has been received and routed to your area Field Support Officer. They will review the uploaded documents and schedule a physical home verification.'}
              </p>
            </div>
          )}

          {isFlagged && (
            <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-sm">
              <div className="font-bold flex items-center gap-2 mb-1 text-amber-900">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                <span>{isDualLanguage ? 'آفیسر فالو اپ نوٹ' : 'Officer Follow-up Note'}</span>
              </div>
              <p className="text-amber-800 text-xs leading-relaxed bg-white p-3 rounded-xl border border-amber-200">
                {latestCase.flag_reason || (isDualLanguage
                  ? 'براہ کرم اصل دستاویزات تیار رکھیں'
                  : 'Please keep the original physical documents ready for the Field Officer during their home visit.')}
              </p>
            </div>
          )}

          {isVerified && latestCase.fso_review_notes && (
            <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-sm">
              <div className="font-bold flex items-center gap-2 mb-1 text-emerald-900">
                <ShieldCheck className="w-4 h-4 text-emerald-600" />
                <span>{isDualLanguage ? 'آفیسر کا جائزہ' : 'Officer Review'}</span>
              </div>
              <p className="text-emerald-800 text-xs bg-white p-3 rounded-xl border border-emerald-200 font-mono">
                {latestCase.fso_review_notes}
              </p>
            </div>
          )}

          {/* Region + FSO info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <span className="text-slate-400 font-medium uppercase tracking-wider block mb-1">
                {isDualLanguage ? 'علاقائی کلسٹر' : 'Regional Cluster'}
              </span>
              <span className="font-bold text-slate-900">
                {latestCase.routing_reason || (isDualLanguage ? 'علاقہ تفویض کیا جا رہا ہے' : 'Region being assigned')}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-xs">
              <span className="text-slate-400 font-medium uppercase tracking-wider block mb-1">
                {isDualLanguage ? 'مختص آفیسر' : 'In-Charge Officer'}
              </span>
              <span className="font-bold text-slate-900">
                {latestCase.assigned_fso_name
                  ? latestCase.assigned_fso_name
                  : latestCase.assigned_fso_id
                  ? 'Assigned FSO'
                  : (isDualLanguage ? 'تفویض کیا جا رہا ہے' : 'Being assigned')}
              </span>
            </div>
          </div>

          {/* Timeline */}
          <div className="pt-3 border-t border-slate-100 flex flex-wrap gap-4 text-xs text-slate-400">
            <span>{isDualLanguage ? 'جمع کرایا' : 'Submitted'}: {new Date(latestCase.created_at).toLocaleDateString()}</span>
            {latestCase.submitted_at && (
              <span>{isDualLanguage ? 'جمع' : 'Sent'}: {new Date(latestCase.submitted_at).toLocaleDateString()}</span>
            )}
            {latestCase.verified_at && (
              <span>{isDualLanguage ? 'تصدیق' : 'Verified'}: {new Date(latestCase.verified_at).toLocaleDateString()}</span>
            )}
          </div>
        </div>
      </div>

      {/* Donor & Aid Status (read-only — maintained by the FSO on the same record) */}
      {isVerified && (
        <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6">
          <h3 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
            <HeartHandshake className="w-4 h-4 text-emerald-600" />
            <span>{isDualLanguage ? 'عطیہ دہندہ اور امدادی حیثیت' : 'Donor & Aid Status'}</span>
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-xl px-4 py-3">
              <span className="text-sm font-semibold text-slate-700">
                {isDualLanguage ? 'کیا عطیہ دہندہ مقرر ہے؟' : 'Donor Arranged?'}
              </span>
              {donorArranged ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 text-emerald-800 border border-emerald-200 text-sm font-bold">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  {isDualLanguage ? 'جی ہاں' : 'Yes'}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 text-slate-600 border border-slate-200 text-sm font-bold">
                  <Clock className="w-4 h-4 text-slate-400" />
                  {isDualLanguage ? 'نہیں' : 'No'}
                </span>
              )}
            </div>

            <div>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">
                {isDualLanguage ? 'امدادی منتقلی کا ریکارڈ' : 'Aid Transfer Log'}
              </span>
              {aidLog.length > 0 ? (
                <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden">
                  <div className="grid grid-cols-2 bg-slate-50 px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    <span>{isDualLanguage ? 'تاریخ' : 'Date'}</span>
                    <span>{isDualLanguage ? 'رقم (روپے)' : 'Amount (PKR)'}</span>
                  </div>
                  {aidLog.map((t, i) => (
                    <div key={i} className="grid grid-cols-2 px-4 py-2.5 text-sm bg-white">
                      <span className="text-slate-600">{t.date}</span>
                      <span className="font-bold text-slate-900">{t.amount.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400 italic">
                  {isDualLanguage
                    ? 'ابھی تک کوئی امدادی منتقلی درج نہیں ہوئی۔'
                    : 'No aid transfers have been recorded yet.'}
                </p>
              )}
            </div>
            <p className="text-[11px] text-slate-400">
              {isDualLanguage
                ? 'یہ معلومات صرف فیلڈ سپورٹ آفیسر اپ ڈیٹ کرتا ہے۔'
                : 'This information is maintained by your Field Support Officer.'}
            </p>
          </div>
        </div>
      )}

      {/* Document Summary */}
      {documents.length > 0 && (
        <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6">
          <h3 className="text-base font-bold text-slate-900 mb-4 flex items-center gap-2">
            <FileText className="w-4 h-4 text-emerald-600" />
            <span>{isDualLanguage ? 'دستاویز خلاصہ' : 'Document Summary'}</span>
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {documents.map((doc: any) => (
              <div key={doc.doc_type} className="bg-slate-50 rounded-xl border border-slate-200 p-3 text-center">
                <p className="text-xs font-semibold text-slate-700 capitalize mb-1">
                  {doc.doc_type.replace(/_/g, ' ')}
                </p>
                {doc.imageUrl ? (
                  <img
                    src={doc.imageUrl}
                    alt={doc.doc_type}
                    className="w-full h-16 object-cover rounded-lg border border-slate-100"
                  />
                ) : (
                  <div className="w-full h-16 bg-slate-100 rounded-lg flex items-center justify-center">
                    <FileText className="w-4 h-4 text-slate-300" />
                  </div>
                )}
                <p className="text-[10px] text-slate-400 mt-1">{doc.status}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Compiled details */}
      {compiled && (
        <div className="bg-white rounded-3xl border border-slate-200 shadow-sm p-6">
          <h3 className="text-base font-bold text-slate-900 mb-4">
            {isDualLanguage ? 'خاندان اور بچے کی تفصیلات' : 'Family & Child Details'}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <DetailCard
              title={isDualLanguage ? 'بچے کی معلومات' : 'Child Information'}
              items={[
                { label: 'Child Name', value: compiled.childDetails?.name },
                { label: 'CRC Number', value: compiled.childDetails?.crcOrRegNumber },
                { label: 'Date of Birth', value: compiled.childDetails?.dateOfBirth },
              ]}
            />
            <DetailCard
              title={isDualLanguage ? 'خاندانی معلومات' : 'Family Information'}
              items={[
                { label: 'Father Name', value: compiled.fatherDetails?.name },
                { label: 'Mother Name', value: compiled.motherDetails?.name },
                { label: 'Address', value: compiled.residentialAddress },
              ]}
            />
          </div>
        </div>
      )}
    </div>
  );
};

// ── Profile Card ─────────────────────────────────────────────────────────

function ProfileCard({ user, isDualLanguage }: { user: AppUser; isDualLanguage: boolean }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-2xl bg-emerald-100 border border-emerald-200 flex items-center justify-center text-emerald-800 font-bold text-lg shrink-0">
          {user.name.charAt(0)}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-bold text-slate-900">{user.name}</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              {isDualLanguage ? 'یتیم خاندان' : 'Orphan Family'}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-3">
            {user.phone && (
              <span className="flex items-center gap-1">
                <Phone className="w-3 h-3" />
                {user.phone}
              </span>
            )}
            {user.city && (
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                {user.city}
              </span>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Status Pill ──────────────────────────────────────────────────────────

function StatusPill({ status, isDualLanguage }: { status: string; isDualLanguage: boolean }) {
  if (status === 'verified') {
    return (
      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-50 text-emerald-800 border border-emerald-200 text-sm font-bold">
        <CheckCircle2 className="w-5 h-5 text-emerald-600" />
        <span>{isDualLanguage ? 'تصدیق شدہ' : 'Verified & Approved'}</span>
      </div>
    );
  }
  if (status === 'flagged') {
    return (
      <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-50 text-amber-900 border border-amber-200 text-sm font-bold">
        <AlertTriangle className="w-5 h-5 text-amber-600" />
        <span>{isDualLanguage ? 'تصحیح درکار' : 'Follow-up Required'}</span>
      </div>
    );
  }
  return (
    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-50 text-blue-900 border border-blue-200 text-sm font-bold">
      <Clock className="w-5 h-5 text-blue-600 animate-pulse" />
      <span>{isDualLanguage ? 'زیرِ تصدیق' : 'Pending Verification'}</span>
    </div>
  );
}

// ── Detail Card ──────────────────────────────────────────────────────────

function DetailCard({ title, items }: { title: string; items: { label: string; value?: string }[] }) {
  return (
    <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
      <span className="font-bold text-slate-700 block text-sm pb-1 border-b border-slate-200">{title}</span>
      {items.map((item) => (
        <div key={item.label}>
          <span className="text-slate-400 block">{item.label}:</span>
          <span className="font-semibold text-slate-900">{item.value || '—'}</span>
        </div>
      ))}
    </div>
  );
}
