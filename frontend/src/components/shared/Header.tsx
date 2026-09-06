import React from 'react';
import { AppUser } from '../../types';
import { BrandLogo } from './BrandLogo';
import {
  Globe,
  PlusCircle,
  ShieldCheck,
  User,
  LogOut,
  Building,
} from 'lucide-react';

interface HeaderProps {
  user: AppUser;
  onSignOut: () => void;
  currentTab: 'queue' | 'intake' | 'archive' | 'admin';
  setCurrentTab: (tab: 'queue' | 'intake' | 'archive' | 'admin') => void;
  isDualLanguage: boolean;
  setIsDualLanguage: (val: boolean) => void;
  intakeStep: 1 | 2 | 3;
}

export const Header: React.FC<HeaderProps> = ({
  user,
  onSignOut,
  currentTab,
  setCurrentTab,
  isDualLanguage,
  setIsDualLanguage,
  intakeStep,
}) => {
  const role = user.role;

  const roleLabel =
    role === 'admin'
      ? 'Admin HQ'
      : role === 'fso'
      ? 'FSO Officer'
      : 'Family Portal';

  const roleBadgeColor =
    role === 'admin'
      ? 'bg-purple-950/80 border-purple-700 text-purple-300'
      : role === 'fso'
      ? 'bg-indigo-950/80 border-indigo-700 text-indigo-300'
      : 'bg-emerald-950/80 border-emerald-700 text-emerald-300';

  return (
    <header className="sticky top-0 z-40 shadow-sm">
      {/* ── Main Top Bar ─────────────────────────────────────────────────────── */}
      <div className="bg-slate-900 text-white px-4 sm:px-6 lg:px-8 py-2.5 border-b border-slate-800">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Logo */}
          <BrandLogo size="md" dark isDualLanguage={isDualLanguage} tagline={
            isDualLanguage ? 'کفالت یتامیٰ پروگرام' : 'Orphan Family Support Program'
          } />

          {/* ── FSO Navigation Tabs ────────────────────────────────────────── */}
          {role === 'fso' && (
            <nav className="hidden md:flex items-center space-x-1 bg-slate-950/80 p-1 rounded-xl border border-slate-800">
              <button
                onClick={() => setCurrentTab('queue')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  currentTab === 'queue'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>{isDualLanguage ? 'تصدیقی قطار' : 'Verification Queue'}</span>
              </button>

              <button
                onClick={() => setCurrentTab('intake')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  currentTab === 'intake'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                <PlusCircle className="w-3.5 h-3.5" />
                <span>{isDualLanguage ? 'دستاویزی اندراج' : 'Manual Intake'}</span>
              </button>

              <button
                onClick={() => setCurrentTab('archive')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  currentTab === 'archive'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                <span>{isDualLanguage ? 'ریکارڈ اور تلاش' : 'Records & Search'}</span>
              </button>
            </nav>
          )}

          {/* ── Admin Navigation ───────────────────────────────────────────── */}
          {role === 'admin' && (
            <nav className="hidden md:flex items-center space-x-1 bg-slate-950/80 p-1 rounded-xl border border-slate-800">
              <button
                onClick={() => setCurrentTab('admin')}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  currentTab === 'admin'
                    ? 'bg-purple-700 text-white shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                <Building className="w-3.5 h-3.5" />
                <span>{isDualLanguage ? 'ایڈمن ڈیش بورڈ' : 'Admin Dashboard'}</span>
              </button>
            </nav>
          )}

          {/* ── Right Controls ─────────────────────────────────────────────── */}
          <div className="flex items-center space-x-2.5 sm:space-x-3">
            {/* Language Toggle */}
            <button
              onClick={() => setIsDualLanguage(!isDualLanguage)}
              title="Toggle Urdu/English"
              className={`flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-bold transition-all border cursor-pointer ${
                isDualLanguage
                  ? 'bg-emerald-600 text-white border-emerald-500'
                  : 'bg-slate-800 text-slate-300 border-slate-700 hover:text-white'
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span>{isDualLanguage ? 'اردو' : 'EN'}</span>
            </button>

            {/* User Badge */}
            <div
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-xl text-xs font-bold transition-all border cursor-default ${roleBadgeColor}`}
            >
              {role === 'admin' ? (
                <Building className="w-3.5 h-3.5 text-purple-400" />
              ) : role === 'fso' ? (
                <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
              ) : (
                <User className="w-3.5 h-3.5 text-emerald-400" />
              )}
              <div className="flex items-center space-x-1.5">
                <span className="font-semibold text-white max-w-[120px] sm:max-w-[150px] truncate">
                  {user.name}
                </span>
                <span className="text-[10px] opacity-70 hidden sm:inline">({roleLabel})</span>
              </div>
            </div>

            {/* Sign Out */}
            <button
              onClick={onSignOut}
              className="p-1.5 rounded-lg bg-slate-800/80 hover:bg-rose-950/50 border border-slate-700 hover:border-rose-700 text-slate-400 hover:text-rose-300 transition-colors cursor-pointer"
              title="Sign Out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* ── Intake Stepper Sub-nav (FSO only, during intake) ──────────────── */}
      {role === 'fso' && currentTab === 'intake' && (
        <nav className="bg-white border-b border-slate-200 px-4 sm:px-6 lg:px-8 py-2.5 shadow-sm">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-4 sm:gap-8 text-xs sm:text-sm font-medium overflow-x-auto py-0.5">
              {/* Step 1 */}
              <div
                className={`flex items-center gap-2 ${
                  intakeStep === 1
                    ? 'text-indigo-600 border-b-2 border-indigo-600 pb-1.5 -mb-2.5 font-bold'
                    : 'text-slate-500'
                }`}
              >
                <span
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                    intakeStep === 1
                      ? 'bg-indigo-600 text-white'
                      : 'border border-slate-300 text-slate-500'
                  }`}
                >
                  1
                </span>
                <span>{isDualLanguage ? 'دستاویزات اپلوڈ' : 'Upload Documents'}</span>
              </div>

              {/* Step 2 */}
              <div
                className={`flex items-center gap-2 ${
                  intakeStep === 2
                    ? 'text-indigo-600 border-b-2 border-indigo-600 pb-1.5 -mb-2.5 font-bold'
                    : 'text-slate-500'
                }`}
              >
                <span
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                    intakeStep === 2
                      ? 'bg-indigo-600 text-white'
                      : 'border border-slate-300 text-slate-500'
                  }`}
                >
                  2
                </span>
                <span>{isDualLanguage ? 'تصدیق و جائزہ' : 'Review & Cross-Checks'}</span>
              </div>

              {/* Step 3 */}
              <div
                className={`flex items-center gap-2 ${
                  intakeStep === 3
                    ? 'text-indigo-600 border-b-2 border-indigo-600 pb-1.5 -mb-2.5 font-bold'
                    : 'text-slate-500'
                }`}
              >
                <span
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                    intakeStep === 3
                      ? 'bg-indigo-600 text-white'
                      : 'border border-slate-300 text-slate-500'
                  }`}
                >
                  3
                </span>
                <span>{isDualLanguage ? 'حتمی اندراج' : 'Summary & Submit'}</span>
              </div>
            </div>
          </div>
        </nav>
      )}
    </header>
  );
};
