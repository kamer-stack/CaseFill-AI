import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Lock,
  Eye,
  EyeOff,
  AlertCircle,
  X,
  FileText,
  BadgeCheck,
  RefreshCw,
} from 'lucide-react';
import { AppUser } from '../../types';
import { authApi } from '../../lib/api';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: AppUser, token: string) => void;
  isDualLanguage: boolean;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  isDualLanguage,
}) => {
  const [accountType, setAccountType] = useState<'official' | 'family'>('family');

  // Form fields
  const [cnic, setCnic] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Validation & loading
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // "Forgot password?" reveals an inline note instead of a dead link —
  // there's no self-service reset flow, so this points to the real process.
  const [showForgotInfo, setShowForgotInfo] = useState(false);

  // Reset form fields (not the selected tab) whenever the modal opens
  useEffect(() => {
    if (isOpen) {
      setErrorMessage(null);
      setCnic('');
      setPassword('');
      setShowForgotInfo(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // ── Helpers ────────────────────────────────────────────────────────────────

  const formatCnic = (val: string) => {
    const digits = val.replace(/\D/g, '').slice(0, 13);
    if (digits.length <= 5) return digits;
    if (digits.length <= 12) return `${digits.slice(0, 5)}-${digits.slice(5)}`;
    return `${digits.slice(0, 5)}-${digits.slice(5, 12)}-${digits.slice(12)}`;
  };

  const handleCnicChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCnic(formatCnic(e.target.value));
    setErrorMessage(null);
  };

  const switchTab = (type: 'official' | 'family') => {
    setAccountType(type);
    setErrorMessage(null);
    setShowForgotInfo(false);
  };

  // ── Submit ─────────────────────────────────────────────────────────────────

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cnicDigits = cnic.replace(/\D/g, '');
    if (cnicDigits.length !== 13) {
      setErrorMessage('Please enter a valid 13-digit National CNIC (e.g. 35202-1234567-8).');
      return;
    }

    setIsSubmitting(true);

    try {
      const res = await authApi.signin({
        cnic,
        password,
        expected_account_type: accountType,
      });

      const u = res.user;
      const user: AppUser = {
        id: u.id,
        name: u.name,
        cnic: u.cnic,
        phone: u.phone || '',
        email: u.email,
        role: u.role,
        account_type: u.account_type,
        designation: u.designation,
        badge: u.badge,
        fso_id: u.fso_id,
        assigned_region_id: u.assigned_region_id,
        area_address: u.area_address,
        city: u.city,
      };

      onSuccess(user, res.token);
    } catch (err: any) {
      setErrorMessage(err.message || 'Authentication error. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm overflow-y-auto">
      <div className="relative bg-gradient-to-br from-emerald-50 via-white to-emerald-50 border border-emerald-100 w-full max-w-md rounded-3xl shadow-2xl overflow-hidden my-6">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-10 p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-white/70 transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header: logo + program name */}
        <div className="px-6 sm:px-8 pt-8 pb-5 text-center space-y-3">
          <div className="w-14 h-14 rounded-2xl bg-white border border-emerald-200 shadow-sm flex items-center justify-center mx-auto">
            <ShieldCheck className="w-7 h-7 text-emerald-600" />
          </div>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-wider text-emerald-700">
              Alkhidmat Foundation Pakistan
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              {isDualLanguage ? 'کفالت یتامیٰ پروگرام (OFSP)' : 'Orphan Family Support Program (OFSP)'}
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="px-6 sm:px-8">
          <div className="flex border-b border-slate-200">
            <button
              type="button"
              onClick={() => switchTab('official')}
              className={`flex-1 pb-3 text-xs sm:text-sm font-semibold text-center transition-colors cursor-pointer border-b-2 ${
                accountType === 'official'
                  ? 'text-emerald-700 border-emerald-600'
                  : 'text-slate-400 border-transparent hover:text-slate-600'
              }`}
            >
              {isDualLanguage ? 'الخدمت اہلکار (FSO)' : 'Alkhidmat Official (FSO)'}
            </button>
            <button
              type="button"
              onClick={() => switchTab('family')}
              className={`flex-1 pb-3 text-xs sm:text-sm font-semibold text-center transition-colors cursor-pointer border-b-2 ${
                accountType === 'family'
                  ? 'text-emerald-700 border-emerald-600'
                  : 'text-slate-400 border-transparent hover:text-slate-600'
              }`}
            >
              {isDualLanguage ? 'یتیم خاندان' : 'Beneficiary Family'}
            </button>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 sm:px-8 py-6 space-y-4 max-h-[65vh] overflow-y-auto">
          <div>
            <h2 className="text-xl font-bold text-slate-900">
              {isDualLanguage ? 'کیس فل میں سائن ان کریں' : 'Sign In to CaseFill'}
            </h2>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              {accountType === 'official'
                ? (isDualLanguage
                    ? 'اپنی مختص علاقائی تصدیقی قطار اور خاندانی فائلوں تک رسائی حاصل کریں۔'
                    : 'Access your assigned regional verification queue and family dossiers.')
                : (isDualLanguage
                    ? 'اپنے کیس کی حیثیت دیکھیں اور دستاویزات ٹریک کریں۔'
                    : 'Track your case status and view your submitted documents.')}
            </p>
            <p className="text-[11px] text-rose-500 mt-2">
              * {isDualLanguage ? 'لازمی خانے' : 'Indicates required fields'}
            </p>
          </div>

          {errorMessage && (
            <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start space-x-2.5">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{errorMessage}</div>
            </div>
          )}

          {/* CNIC */}
          <div className="space-y-1">
            <label className="block text-xs font-bold text-slate-700">
              {accountType === 'official'
                ? (isDualLanguage ? 'آفیسر کا شناختی کارڈ نمبر' : 'Officer CNIC')
                : (isDualLanguage ? 'والدہ/سرپرست شناختی کارڈ نمبر' : 'Parent / Guardian CNIC')}{' '}
              <span className="text-rose-500">*</span>
            </label>
            <div className="relative">
              <FileText className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              <input
                type="text"
                required
                value={cnic}
                onChange={handleCnicChange}
                placeholder="00000-0000000-0"
                className="w-full pl-10 pr-3.5 py-2.5 bg-white border border-slate-200 rounded-xl text-xs font-mono font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <p className="text-[10px] text-slate-400">13-digit National CNIC format (XXXXX-XXXXXXX-X).</p>
          </div>

          {/* Password */}
          <div className="space-y-1">
            <label className="block text-xs font-bold text-slate-700">
              Password <span className="text-rose-500">*</span>
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your secure password"
                className="w-full pl-10 pr-10 py-2.5 bg-white border border-slate-200 rounded-xl text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-3 text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Remember + Forgot password */}
          <div className="flex items-center justify-between text-xs">
            <label className="flex items-center gap-2 text-slate-500 cursor-pointer select-none">
              <input type="checkbox" className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
              <span>{isDualLanguage ? 'یہ ڈیوائس یاد رکھیں' : 'Remember this device'}</span>
            </label>
            <button
              type="button"
              onClick={() => setShowForgotInfo((v) => !v)}
              className="text-emerald-700 font-semibold hover:text-emerald-800 cursor-pointer"
            >
              {isDualLanguage ? 'پاسورڈ بھول گئے؟' : 'Forgot password?'}
            </button>
          </div>

          {showForgotInfo && (
            <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-[11px] text-emerald-800 leading-relaxed">
              {isDualLanguage
                ? 'پاسورڈ ری سیٹ خودکار نہیں ہے۔ براہ کرم اپنے ایڈمن یا مختص فیلڈ سپورٹ آفیسر سے رابطہ کریں۔'
                : "Password resets aren't self-service. Please contact your Admin or assigned Field Support Officer to reset your password."}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 px-4 rounded-full bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-md cursor-pointer"
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Signing In...</span>
              </>
            ) : (
              <>
                <BadgeCheck className="w-4 h-4" />
                <span>
                  {accountType === 'official' ? 'Sign In to Verification Portal' : 'Sign In to Family Portal'}
                </span>
              </>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="px-6 sm:px-8 py-3 border-t border-slate-100 bg-slate-50/70 flex flex-col sm:flex-row items-center justify-between gap-1 text-[10px] text-slate-400">
          <span>&copy; {new Date().getFullYear()} Alkhidmat Foundation Pakistan &bull; Orphan Family Support Program</span>
          <span>
            {isDualLanguage
              ? 'مدد کے لیے اپنے مقامی الخدمت دفتر سے رابطہ کریں'
              : 'For help, contact your local Alkhidmat Foundation office'}
          </span>
        </div>
      </div>
    </div>
  );
};
