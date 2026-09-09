import React, { useState, useRef } from 'react';
import { DocumentSlotConfig, DocType } from '../../types';
import { casesApi } from '../../lib/api';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ImagePlus,
  FileText,
  ArrowRight,
  RefreshCw,
  Trash2,
  Upload,
  Sparkles,
} from 'lucide-react';

interface UploadScreenProps {
  slots: DocumentSlotConfig[];
  setSlots: React.Dispatch<React.SetStateAction<DocumentSlotConfig[]>>;
  extractedData: Record<string, any>;
  setExtractedData: React.Dispatch<React.SetStateAction<Record<string, any>>>;
  caseId: string | null;
  setCaseId: React.Dispatch<React.SetStateAction<string | null>>;
  onStartTimer: () => void;
  onProceed: () => void;
  isDualLanguage: boolean;
  targetChildName: string;
  setTargetChildName: React.Dispatch<React.SetStateAction<string>>;
  targetChildRegNumber: string;
  setTargetChildRegNumber: React.Dispatch<React.SetStateAction<string>>;
}

// 13-digit Pakistani CNIC, e.g. 00000-0000000-0
const CNIC_FORMAT_RE = /^\d{5}-\d{7}-\d{1}$/;

const EDUCATION_OPTIONS = [
  { value: 'none', label: 'None', urdu: 'کوئی نہیں' },
  { value: 'primary', label: 'Primary', urdu: 'پرائمری' },
  { value: 'middle', label: 'Middle', urdu: 'مڈل' },
  { value: 'matric', label: 'Matric', urdu: 'میٹرک' },
  { value: 'intermediate', label: 'Intermediate', urdu: 'انٹرمیڈیٹ' },
  { value: 'graduate', label: 'Graduate', urdu: 'گریجویٹ' },
  { value: 'post-graduate', label: 'Post-Graduate', urdu: 'پوسٹ گریجویٹ' },
];

export const UploadScreen: React.FC<UploadScreenProps> = ({
  slots,
  setSlots,
  extractedData,
  setExtractedData,
  caseId,
  setCaseId,
  onStartTimer,
  onProceed,
  isDualLanguage,
  targetChildName,
  setTargetChildName,
  targetChildRegNumber,
  setTargetChildRegNumber,
}) => {
  const [targetChildNameTouched, setTargetChildNameTouched] = useState(false);
  const targetChildNameShowError = targetChildNameTouched && targetChildName.trim().length === 0;
  const [addressText, setAddressText] = useState('');
  const [educationText, setEducationText] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // Only flag the CNIC as invalid once it's fully typed (13 digits) —
  // never mid-keystroke, since a partial value is expected to look
  // "incomplete" while the FSO is still writing it.
  const targetChildCnicDigitCount = targetChildRegNumber.replace(/\D/g, '').length;
  const targetChildCnicComplete = targetChildCnicDigitCount >= 13;
  const targetChildCnicValid = CNIC_FORMAT_RE.test(targetChildRegNumber.trim());
  const targetChildCnicShowError = targetChildCnicComplete && !targetChildCnicValid;

  // CNIC format toggle — determines extraction route on the backend:
  // "old" -> OCR.space + Qwen-plus text structuring (no printed English
  // field labels on the card). "new" -> existing Qwen-VL vision path.
  // Only meaningful for mother_cnic/father_cnic; ignored for other slots.
  const [cnicFormats, setCnicFormats] = useState<Record<string, 'old' | 'new'>>({
    mother_cnic: 'new',
    father_cnic: 'new',
  });

  const doneCount = slots.filter(
    (s) => s.status === 'done' || s.status === 'not_provided'
  ).length;

  // ── Ensure case exists ──────────────────────────────────────────────────

  const ensureCase = async (): Promise<string> => {
    if (caseId) return caseId;
    setIsCreating(true);
    try {
      const res = await casesApi.create('fso_manual');
      setCaseId(res.case_id);
      onStartTimer();
      return res.case_id;
    } finally {
      setIsCreating(false);
    }
  };

  // ── File upload + extract ──────────────────────────────────────────────

  const handleFileSelect = async (slotId: DocType, file: File) => {
    // Update slot to uploading
    updateSlot(slotId, { status: 'uploading', errorMessage: undefined });

    try {
      const cid = await ensureCase();

      // Upload file
      const uploadRes = await casesApi.uploadDocument(cid, slotId, file);
      updateSlot(slotId, {
        status: 'extracting',
        file: { name: file.name, previewUrl: uploadRes.image_url },
      });

      // Extract with AI
      const isCnicSlot = slotId === 'mother_cnic' || slotId === 'father_cnic';
      const extractRes = await casesApi.extract(
        cid,
        slotId,
        undefined,
        isCnicSlot ? cnicFormats[slotId] : undefined,
        slotId === 'b_form' && targetChildRegNumber.trim() ? targetChildRegNumber.trim() : undefined,
        slotId === 'b_form' && targetChildName.trim() ? targetChildName.trim() : undefined
      );

      updateSlot(slotId, { status: 'done' });
      setExtractedData((prev) => ({
        ...prev,
        [slotId]: extractRes.extracted,
      }));
    } catch (err: any) {
      updateSlot(slotId, {
        status: 'error',
        errorMessage: err.message || 'Upload/extraction failed',
      });
    }
  };

  // ── Text-only saves ───────────────────────────────────────────────────

  const saveAddress = () => {
    if (!addressText.trim()) return;
    setExtractedData((prev) => ({
      ...prev,
      address: { full_address: addressText.trim() },
    }));
    updateSlot('address', { status: 'done' });
  };

  const saveEducation = () => {
    if (!educationText) return;
    const opt = EDUCATION_OPTIONS.find((o) => o.value === educationText);
    setExtractedData((prev) => ({
      ...prev,
      mother_education: { education_level: educationText, label: opt?.label || educationText },
    }));
    updateSlot('mother_education', { status: 'done' });
  };

  // ── Not provided / retry ──────────────────────────────────────────────

  const markNotProvided = async (slotId: DocType) => {
    try {
      const cid = await ensureCase();
      await casesApi.markNotProvided(cid, slotId, 'Marked by FSO during intake');
    } catch {
      // Silently continue — backend tracking is optional
    }
    updateSlot(slotId, { status: 'not_provided', notProvidedReason: 'Marked by FSO' });
  };

  const retrySlot = (slotId: DocType) => {
    updateSlot(slotId, { status: 'empty', errorMessage: undefined, file: undefined });
    setExtractedData((prev) => {
      const copy = { ...prev };
      delete copy[slotId];
      return copy;
    });
  };

  // Delete an uploaded document image (pre-submission only) so the FSO can re-upload it
  const removeDocument = async (slotId: DocType) => {
    try {
      if (caseId) await casesApi.deleteDocument(caseId, slotId);
    } catch {
      // Backend tracking is best-effort; local state still resets
    }
    retrySlot(slotId);
  };

  // ── Helpers ────────────────────────────────────────────────────────────

  const updateSlot = (id: DocType, patch: Partial<DocumentSlotConfig>) => {
    setSlots((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  };

  const triggerFileInput = (slotId: DocType) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*,.heic,.heif';
    input.onchange = () => {
      if (input.files && input.files[0]) {
        handleFileSelect(slotId, input.files[0]);
      }
    };
    input.click();
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {isDualLanguage ? 'دستاویزات اپلوڈ' : 'Document Upload'}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {isDualLanguage
              ? 'OFSP کیس کی تصدیق کے لیے دستاویزات اپلوڈ کریں'
              : 'Upload documents for OFSP case verification'}
          </p>
        </div>
        <button
          onClick={onProceed}
          disabled={!targetChildName.trim() || !targetChildCnicValid}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-xl shadow-md disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-2 cursor-pointer"
        >
          <span>{isDualLanguage ? 'جائزہ پر جائیں' : 'Continue to Review'}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
      {(!targetChildName.trim() || !targetChildCnicValid) && (
        <p className="text-xs text-amber-600 -mt-2">
          {isDualLanguage
            ? 'جاری رکھنے کے لیے بچے کا نام اور شناختی کارڈ نمبر درکار ہے'
            : "Enter the orphan's name and a valid CNIC above before continuing."}
        </p>
      )}

      {/* Progress Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-slate-700">
            {doneCount} / {slots.length} {isDualLanguage ? 'دستاویزات' : 'documents'}
          </span>
          <span className="text-sm font-mono text-slate-400">
            {Math.round((doneCount / slots.length) * 100)}%
          </span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-2.5">
          <div
            className="bg-emerald-500 h-2.5 rounded-full transition-all duration-500"
            style={{ width: `${(doneCount / slots.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Target Child (B-Form) */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-4">
        <div>
          <label className="text-sm font-semibold text-slate-700 block mb-2">
            {isDualLanguage
              ? "Target Child's Name — بچے کا نام"
              : "Target Child's Name"}
          </label>
          <input
            type="text"
            value={targetChildName}
            onChange={(e) => setTargetChildName(e.target.value)}
            onBlur={() => setTargetChildNameTouched(true)}
            placeholder="e.g. Ali Hassan"
            className={`w-56 px-3 py-2 border rounded-xl text-sm focus:ring-2 outline-none ${
              targetChildNameShowError
                ? 'border-rose-400 focus:ring-rose-500/30 focus:border-rose-500'
                : 'border-slate-300 focus:ring-indigo-500/30 focus:border-indigo-500'
            }`}
          />
          {targetChildNameShowError && (
            <p className="text-xs text-rose-500 mt-1">Name is required.</p>
          )}
        </div>
        <div>
          <label className="text-sm font-semibold text-slate-700 block mb-2">
            {isDualLanguage
              ? "Target Child's CNIC — بچے کا شناختی کارڈ نمبر"
              : "Target Child's CNIC"}
          </label>
          <input
            type="text"
            value={targetChildRegNumber}
            onChange={(e) => setTargetChildRegNumber(e.target.value)}
            placeholder="e.g. 00000-0000000-0"
            className={`w-56 px-3 py-2 border rounded-xl text-sm focus:ring-2 outline-none ${
              targetChildCnicShowError
                ? 'border-rose-400 focus:ring-rose-500/30 focus:border-rose-500'
                : 'border-slate-300 focus:ring-indigo-500/30 focus:border-indigo-500'
            }`}
          />
          <p className="text-xs text-slate-400 mt-1">
            13 digits, format 00000-0000000-0. We use it to auto-match the
            right child after extraction and flag it if it doesn't match.
          </p>
          {targetChildCnicShowError && (
            <p className="text-xs text-rose-500 mt-1">
              That doesn't look like a valid CNIC — check the format.
            </p>
          )}
        </div>
      </div>

      {/* Upload Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {slots.map((slot) => (
          <div
            key={slot.id}
            className={`bg-white rounded-2xl border shadow-sm overflow-hidden transition-all ${
              slot.status === 'done'
                ? 'border-emerald-300'
                : slot.status === 'not_provided'
                ? 'border-slate-200 bg-slate-50'
                : slot.status === 'error'
                ? 'border-rose-300'
                : 'border-slate-200'
            }`}
          >
            <div className="p-5">
              {/* Label row */}
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">{slot.title}</h3>
                  {isDualLanguage && (
                    <p className="text-xs font-urdu text-slate-500 mt-0.5" dir="rtl">
                      {slot.urduTitle}
                    </p>
                  )}
                  <p className="text-xs text-slate-400 mt-0.5">{slot.subtitle}</p>
                </div>
                <SlotStatusIcon status={slot.status} />
              </div>

              {/* Content area */}
              {slot.isInputOnly ? (
                /* ── Text Input Slots ─────────────────────────────────── */
                slot.status === 'done' ? (
                  <div className="bg-emerald-50 rounded-xl p-3 text-sm text-emerald-800 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span className="truncate">
                      {slot.id === 'address'
                        ? (extractedData.address?.full_address as string)
                        : (extractedData.mother_education?.label as string) || (extractedData.mother_education?.education_level as string)}
                    </span>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {slot.id === 'address' ? (
                      <textarea
                        value={addressText}
                        onChange={(e) => setAddressText(e.target.value)}
                        placeholder="Type the full residential address..."
                        rows={2}
                        className="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 outline-none resize-none"
                      />
                    ) : (
                      <select
                        value={educationText}
                        onChange={(e) => setEducationText(e.target.value)}
                        className="w-full px-3 py-2 border border-slate-300 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500 outline-none"
                      >
                        <option value="">Select education level...</option>
                        {EDUCATION_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label} — {opt.urdu}
                          </option>
                        ))}
                      </select>
                    )}
                    <div className="flex gap-2">
                      <button
                        onClick={slot.id === 'address' ? saveAddress : saveEducation}
                        disabled={
                          (slot.id === 'address' ? !addressText.trim() : !educationText) ||
                          slot.status === 'uploading'
                        }
                        className="px-3 py-1.5 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-700 disabled:opacity-40 transition-colors cursor-pointer"
                      >
                        {isDualLanguage ? 'محفوظ کریں' : 'Save'}
                      </button>
                      <button
                        onClick={() => markNotProvided(slot.id)}
                        className="px-3 py-1.5 border border-slate-300 text-slate-600 text-xs rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
                      >
                        {isDualLanguage ? 'فراہم نہیں' : 'Not Provided'}
                      </button>
                    </div>
                  </div>
                )
              ) : slot.status === 'done' && slot.file ? (
                /* ── Done: Thumbnail + Replace/Remove ────────────────── */
                <div className="flex items-center gap-3">
                  <img
                    src={slot.file.previewUrl}
                    alt={slot.title}
                    className="w-16 h-16 object-cover rounded-xl border border-slate-200"
                  />
                  <div className="min-w-0">
                    <div className="text-sm text-emerald-700 font-medium flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>{isDualLanguage ? 'کامیابی سے نکالا گیا' : 'Extracted successfully'}</span>
                    </div>
                    <div className="flex items-center gap-3 mt-1.5">
                      <button
                        onClick={() => triggerFileInput(slot.id)}
                        className="text-xs text-indigo-600 hover:text-indigo-800 font-bold flex items-center gap-1 cursor-pointer"
                      >
                        <RefreshCw className="w-3 h-3" />
                        <span>{isDualLanguage ? 'تبدیل کریں' : 'Replace'}</span>
                      </button>
                      <button
                        onClick={() => removeDocument(slot.id)}
                        className="text-xs text-rose-500 hover:text-rose-700 font-bold flex items-center gap-1 cursor-pointer"
                      >
                        <Trash2 className="w-3 h-3" />
                        <span>{isDualLanguage ? 'حذف کریں' : 'Remove'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              ) : slot.status === 'not_provided' ? (
                /* ── Not Provided ──────────────────────────────────── */
                <div className="space-y-2">
                  <div className="text-sm text-slate-400 italic flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />
                    <span>{isDualLanguage ? 'فراہم نہیں کیا گیا' : 'Marked as not provided'}</span>
                  </div>
                  <button
                    onClick={() => removeDocument(slot.id)}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-bold flex items-center gap-1 cursor-pointer"
                  >
                    <Upload className="w-3 h-3" />
                    <span>{isDualLanguage ? 'دوبارہ اپلوڈ کریں' : 'Undo & upload document'}</span>
                  </button>
                </div>
              ) : slot.status === 'error' ? (
                /* ── Error ───────────────────────────────────────────── */
                <div className="space-y-2">
                  <div className="text-sm text-rose-600 bg-rose-50 rounded-xl p-2.5 flex items-start gap-2">
                    <XCircle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span className="truncate">{slot.errorMessage?.slice(0, 120)}</span>
                  </div>
                  <button
                    onClick={() => retrySlot(slot.id)}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-bold flex items-center gap-1 cursor-pointer"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>{isDualLanguage ? 'دوبارہ کوشش' : 'Try again'}</span>
                  </button>
                </div>
              ) : (
                /* ── Drop Zone ───────────────────────────────────────── */
                <div>
                  {(slot.id === 'mother_cnic' || slot.id === 'father_cnic') &&
                    slot.status !== 'uploading' &&
                    slot.status !== 'extracting' && (
                      <div className="mb-3 flex items-center gap-2 bg-slate-50 rounded-lg p-2">
                        <span className="text-xs text-slate-500 font-medium">
                          {isDualLanguage ? 'کارڈ کی قسم:' : 'Card type:'}
                        </span>
                        <div className="flex gap-1">
                          {(['new', 'old'] as const).map((fmt) => (
                            <button
                              key={fmt}
                              type="button"
                              onClick={() =>
                                setCnicFormats((prev) => ({ ...prev, [slot.id]: fmt }))
                              }
                              className={`px-2.5 py-1 text-xs font-bold rounded-md transition-colors cursor-pointer ${
                                cnicFormats[slot.id] === fmt
                                  ? 'bg-indigo-600 text-white'
                                  : 'bg-white text-slate-500 border border-slate-200 hover:border-indigo-300'
                              }`}
                            >
                              {fmt === 'new'
                                ? isDualLanguage
                                  ? 'نیا (بائلنگول)'
                                  : 'New (bilingual)'
                                : isDualLanguage
                                ? 'پرانا'
                                : 'Old'}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  <div
                    onClick={() => {
                      if (slot.status === 'uploading' || slot.status === 'extracting' || isCreating) return;
                      triggerFileInput(slot.id);
                    }}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (e.dataTransfer.files?.[0]) handleFileSelect(slot.id, e.dataTransfer.files[0]);
                    }}
                    className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer ${
                      slot.status === 'uploading' || slot.status === 'extracting' || isCreating
                        ? 'border-slate-200 bg-slate-50 opacity-60'
                        : 'border-slate-300 hover:border-indigo-400 hover:bg-indigo-50/30'
                    }`}
                  >
                    {slot.status === 'uploading' || slot.status === 'extracting' || isCreating ? (
                      slot.status === 'extracting' ? (
                        /* ── Designed "AI is reading your document…" state ── */
                        <div className="flex flex-col items-center gap-3 animate-fade-in-up">
                          {/* Document thumbnail with animated scan line */}
                          <div className="relative w-24 h-24 rounded-xl overflow-hidden border-2 border-emerald-300 shadow-inner">
                            {slot.file?.previewUrl ? (
                              <img
                                src={slot.file.previewUrl}
                                alt={slot.title}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="w-full h-full bg-slate-100 flex items-center justify-center">
                                <FileText className="w-8 h-8 text-slate-300" />
                              </div>
                            )}
                            <div className="ai-scan-overlay" />
                          </div>

                          {/* Reading label */}
                          <div className="flex items-center gap-2">
                            <Sparkles className="w-4 h-4 text-emerald-500 ai-pulse" />
                            <p className="text-sm font-bold text-emerald-700 ai-ellipsis">
                              {isDualLanguage ? 'اے آئی آپ کی دستاویز پڑھ رہی ہے' : 'AI is reading your document'}
                            </p>
                          </div>
                          {isDualLanguage && (
                            <p className="text-xs font-urdu text-emerald-600" dir="rtl">
                              نستعلیق عبارت پڑھی جا رہی ہے، براہ کرم انتظار کریں
                            </p>
                          )}

                          {/* Step hints */}
                          <div className="flex items-center gap-1.5 flex-wrap justify-center">
                            {[
                              isDualLanguage ? 'عبارت پڑھنا' : 'Reading text',
                              isDualLanguage ? 'فیلڈز نکالنا' : 'Extracting fields',
                              isDualLanguage ? 'درستگی جانچنا' : 'Scoring confidence',
                            ].map((step, i) => (
                              <span
                                key={i}
                                className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-600 border border-emerald-200"
                              >
                                {step}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : slot.status === 'uploading' ? (
                        /* ── Upload progress with shimmer bar ── */
                        <div className="flex flex-col items-center gap-3 w-full max-w-[220px] mx-auto">
                          <Upload className="w-6 h-6 text-indigo-400" />
                          <p className="text-xs text-indigo-600 font-semibold ai-ellipsis">
                            {isDualLanguage ? 'اپلوڈ ہو رہا ہے' : 'Uploading document'}
                          </p>
                          <div className="w-full h-1.5 rounded-full overflow-hidden bg-slate-200">
                            <div className="ai-shimmer h-full w-full rounded-full" />
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col items-center gap-2">
                          <div className="w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                          <p className="text-xs text-indigo-600 font-semibold ai-ellipsis">
                            {isDualLanguage ? 'نیا کیس بنا رہا ہے' : 'Creating case'}
                          </p>
                        </div>
                      )
                    ) : (
                      <div className="flex flex-col items-center gap-2">
                        <ImagePlus className="w-8 h-8 text-slate-300" />
                        <p className="text-sm text-slate-500">
                          <span className="text-indigo-600 font-semibold">
                            {isDualLanguage ? 'اپلوڈ کریں' : 'Click to upload'}
                          </span>{' '}
                          {isDualLanguage ? 'یا یہاں ڈراپ کریں' : 'or drag & drop'}
                        </p>
                        <p className="text-xs text-slate-400">PNG, JPG, HEIC, WebP</p>
                      </div>
                    )}
                  </div>
                  {!slot.isMandatory && slot.status === 'empty' && (
                    <button
                      onClick={() => markNotProvided(slot.id)}
                      className="mt-2 text-xs text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
                    >
                      {isDualLanguage ? 'فراہم نہیں کے طور پر نشان زد کریں' : 'Mark as not provided'}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Status Icon ──────────────────────────────────────────────────────────

function SlotStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'done':
      return <CheckCircle2 className="w-5 h-5 text-emerald-500" />;
    case 'uploading':
    case 'extracting':
      return <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />;
    case 'error':
      return <XCircle className="w-5 h-5 text-rose-500" />;
    case 'not_provided':
      return <AlertTriangle className="w-5 h-5 text-slate-300" />;
    default:
      return <FileText className="w-5 h-5 text-slate-300" />;
  }
}