import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Users,
  Lock,
  Eye,
  EyeOff,
  AlertCircle,
  X,
  ArrowRight,
  ArrowLeft,
  FileText,
  BadgeCheck,
  RefreshCw,
} from 'lucide-react';
import { AppUser } from '../../types';
import { authApi } from '../../lib/api';
import { BrandLogo } from '../shared/BrandLogo';

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
  const [step, setStep] = useState<'select_type' | 'form'>('select_type');
  const [accountType, setAccountType] = useState<'official' | 'family'>('family');

  // Form fields
  const [cnic, setCnic] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Validation & loading
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset when modal opens
  useEffect(() => {
    if (isOpen) {
      setStep('select_type');
      setErrorMessage(null);
      setCnic('');
      setPassword('');
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

      // Signin returns DB rows directly (snake_case keys)
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm overflow-y-auto">
      <div className="bg-white border border-slate-200 w-full max-w-lg rounded-3xl shadow-2xl overflow-hidden my-6">
        {/* Modal Header */}
        <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <BrandLogo size="md" dark isDualLanguage={isDualLanguage} tagline={
              isDualLanguage ? 'الخدمت فاؤنڈیشن • کفالت یتامیٰ پروگرام' : 'Orphan Family Support Program'
            } />
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* STEP 1: Account Type Selection */}
        {step === 'select_type' ? (
          <div className="p-6 sm:p-7 space-y-6">
            <div className="text-center space-y-1">
              <h2 className="text-xl font-bold text-slate-900">
                {isDualLanguage ? 'لاگ ان کا انتخاب کریں' : 'Choose Sign-In Pathway'}
              </h2>
              <p className="text-xs text-slate-500">
                {isDualLanguage
                  ? 'براہ کرم منتخب کریں کہ آپ یتیم خاندان ہیں یا الخدمت کے مجاز فیلڈ آفیسر'
                  : 'Select whether you are signing in as an Orphan Family or an Authorized Official'}
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Orphan Family */}
              <button
                type="button"
                onClick={() => { setAccountType('family'); setStep('form'); setErrorMessage(null); }}
                className="p-5 rounded-2xl border-2 border-slate-200 hover:border-emerald-500 hover:bg-emerald-50/40 text-left transition-all group flex flex-col justify-between space-y-4 shadow-sm hover:shadow-md cursor-pointer"
              >
                <div className="space-y-2">
                  <div className="w-11 h-11 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center group-hover:scale-105 transition-transform shadow-sm">
                    <Users className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-slate-900 group-hover:text-emerald-950">
                      Orphan Family
                    </h3>
                    <p className="text-xs font-urdu text-emerald-700 font-semibold mt-0.5" dir="rtl">
                      یتیم خاندان (والدہ / سرپرست)
                    </p>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Access your active case, track verification status, and manage child documentation.
                  </p>
                </div>
                <div className="flex items-center text-xs font-bold text-emerald-600 group-hover:text-emerald-800 pt-2 border-t border-slate-100">
                  <span>Family Sign In</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-1 group-hover:translate-x-1 transition-transform" />
                </div>
              </button>

              {/* Alkhidmat Official */}
              <button
                type="button"
                onClick={() => { setAccountType('official'); setStep('form'); setErrorMessage(null); }}
                className="p-5 rounded-2xl border-2 border-slate-200 hover:border-indigo-500 hover:bg-indigo-50/40 text-left transition-all group flex flex-col justify-between space-y-4 shadow-sm hover:shadow-md cursor-pointer"
              >
                <div className="space-y-2">
                  <div className="w-11 h-11 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center group-hover:scale-105 transition-transform shadow-sm">
                    <ShieldCheck className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="font-bold text-base text-slate-900 group-hover:text-indigo-950">
                      Alkhidmat Official
                    </h3>
                    <p className="text-xs font-urdu text-indigo-700 font-semibold mt-0.5" dir="rtl">
                      الخدمت اہلکار (FSO)
                    </p>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Field Support Officers access regional verification queues and perform home audits.
                  </p>
                </div>
                <div className="flex items-center text-xs font-bold text-indigo-600 group-hover:text-indigo-800 pt-2 border-t border-slate-100">
                  <span>Official Sign In</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-1 group-hover:translate-x-1 transition-transform" />
                </div>
              </button>
            </div>

            <div className="text-center text-[11px] text-slate-400 bg-slate-50 border border-slate-200 rounded-xl p-3 leading-relaxed">
              Accounts are provisioned by Alkhidmat Foundation. There is no self-registration —
              orphan families are registered through their nearest Field Support Officer.
            </div>
          </div>
        ) : (
          /* STEP 2: Sign-In Form */
          <form onSubmit={handleSubmit} className="p-6 sm:p-7 space-y-4 max-h-[82vh] overflow-y-auto">
            {/* Top Nav */}
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <button
                type="button"
                onClick={() => setStep('select_type')}
                className="text-xs text-slate-500 hover:text-slate-900 flex items-center space-x-1 cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Back to Pathways</span>
              </button>

              <span
                className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                  accountType === 'official'
                    ? 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {accountType === 'official' ? 'Official Sign In' : 'Family Sign In'}
              </span>
            </div>

            {/* Error Alert */}
            {errorMessage && (
              <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start space-x-2.5">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div className="flex-1 font-medium">{errorMessage}</div>
              </div>
            )}

            {/* Account Info Note */}
            <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3 text-xs text-slate-600">
              {accountType === 'official' ? (
                <span>
                  <strong>Authorized Official Sign-In:</strong> Sign in with your registered CNIC. <em>FSO accounts are provisioned internally by Central Admin.</em>
                </span>
              ) : (
                <span>
                  <strong>Orphan Family Sign-In:</strong> Sign in with the registered mother's or legal guardian's 13-digit CNIC.
                </span>
              )}
            </div>

            {/* CNIC */}
            <div className="space-y-1">
              <label className="block text-xs font-bold text-slate-700">
                {accountType === 'family'
                  ? 'Parent / Guardian 13-Digit CNIC (شناختی کارڈ نمبر)'
                  : 'Personal 13-Digit CNIC (قومی شناختی کارڈ)'}{' '}
                <span className="text-rose-500">*</span>
              </label>

              <div className="relative">
                <FileText className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="text"
                  required
                  value={cnic}
                  onChange={handleCnicChange}
                  placeholder="00000-0000000-0 (13 digits)"
                  className="w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-medium text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
              <p className="text-[10px] text-slate-400">
                13-digit National CNIC format (XXXXX-XXXXXXX-X).
              </p>
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
                  placeholder="Enter your password"
                  className="w-full pl-10 pr-10 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
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

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className={`w-full py-3 px-4 rounded-xl text-white font-bold text-xs flex items-center justify-center space-x-2 transition-all shadow-md cursor-pointer ${
                accountType === 'official'
                  ? 'bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50'
                  : 'bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50'
              }`}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Signing In...</span>
                </>
              ) : (
                <>
                  <BadgeCheck className="w-4 h-4" />
                  <span>{`Sign In to ${accountType === 'official' ? 'Official' : 'Family'} Portal`}</span>
                </>
              )}
            </button>

            {/* Help Note */}
            <div className="pt-2 text-center text-xs text-slate-500 border-t border-slate-100">
              <span>
                Don't have an account? Please contact your nearest{' '}
                <span className="font-bold text-slate-700">Alkhidmat Foundation office</span> —
                accounts are registered by authorized Field Support Officers.
              </span>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
