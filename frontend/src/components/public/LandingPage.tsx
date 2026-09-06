import React from 'react';
import { BrandLogo } from '../shared/BrandLogo';
import {
  ShieldCheck,
  Users,
  Sparkles,
  ArrowRight,
  Globe,
  CheckCircle2,
  Image as ImageIcon,
  Lock,
} from 'lucide-react';

interface LandingPageProps {
  onOpenAuth: () => void;
  isDualLanguage: boolean;
  setIsDualLanguage: (val: boolean) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onOpenAuth,
  isDualLanguage,
  setIsDualLanguage,
}) => {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans selection:bg-emerald-500 selection:text-slate-950">
      {/* ── Top Navigation Bar ─────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-slate-950/90 backdrop-blur-md border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between">
          {/* Logo */}
          <BrandLogo size="lg" dark isDualLanguage={isDualLanguage} />

          {/* Right Actions */}
          <div className="flex items-center space-x-2.5 sm:space-x-3">
            <button
              onClick={() => setIsDualLanguage(!isDualLanguage)}
              className="px-2.5 py-1.5 rounded-xl bg-slate-800/80 hover:bg-slate-800 border border-slate-700 text-xs text-slate-300 hover:text-white flex items-center space-x-1.5 transition-colors cursor-pointer"
              title="Toggle English / اردو"
            >
              <Globe className="w-3.5 h-3.5 text-emerald-400" />
              <span className="font-semibold text-[11px]">
                {isDualLanguage ? 'اردو / English' : 'English'}
              </span>
            </button>

            <button
              onClick={() => onOpenAuth()}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs border border-slate-700 transition-all hover:border-slate-600 cursor-pointer"
            >
              {isDualLanguage ? 'لاگ ان (Sign In)' : 'Sign In'}
            </button>
          </div>
        </div>
      </header>

      {/* ── Hero Section ───────────────────────────────────────────────────── */}
      <section className="relative pt-12 pb-16 md:pt-16 md:pb-24 border-b border-slate-800 overflow-hidden">
        {/* Background glow */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-emerald-500/10 blur-[120px] pointer-events-none rounded-full" />
        <div className="absolute top-1/3 right-10 w-[400px] h-[300px] bg-indigo-500/10 blur-[120px] pointer-events-none rounded-full" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
            {/* Left Content */}
            <div className="lg:col-span-7 space-y-6 text-left">
              <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-full bg-emerald-950/70 border border-emerald-800/80 text-emerald-300 text-xs font-semibold">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                <span>AI-Assisted Orphan Case Intake &amp; Verification</span>
              </div>

              <div className="space-y-3">
                <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-white tracking-tight leading-[1.15]">
                  Connecting Orphan Families with Alkhidmat's Support
                </h1>
                <p className="text-base sm:text-lg text-slate-300 font-normal leading-relaxed">
                  Streamlining document intake and verification so orphan families can access education sponsorship and monthly stipends faster and more accurately.
                </p>
                {isDualLanguage && (
                  <p className="text-sm sm:text-base font-urdu text-emerald-400 font-medium leading-relaxed" dir="rtl">
                    یتیم خاندانوں کو الخدمت فیملی سپورٹ پروگرام سے جوڑنا، تاکہ تعلیمی و کفالتی کیسز کی تصدیق اور منظوری شفاف، تیز ترین اور آسان ہو۔
                  </p>
                )}
              </div>

              {/* CTA Buttons */}
              <div className="flex flex-wrap items-center gap-3.5 pt-2">
                <button
                  onClick={() => onOpenAuth()}
                  className="px-6 py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm shadow-xl flex items-center space-x-2 transition-all hover:scale-105 active:scale-95 cursor-pointer"
                >
                  <span>{isDualLanguage ? 'اکاؤنٹ میں لاگ ان کریں' : 'Sign In to Your Account'}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>

              {/* Trust Metrics */}
              <div className="grid grid-cols-3 gap-3 pt-4 border-t border-slate-800/80">
                <div className="space-y-0.5">
                  <div className="text-xl font-bold text-white">8 Docs</div>
                  <div className="text-xs text-slate-400">Civil Registry OCR</div>
                </div>
                <div className="space-y-0.5">
                  <div className="text-xl font-bold text-emerald-400">&lt; 3 Mins</div>
                  <div className="text-xs text-slate-400">Intake Duration</div>
                </div>
                <div className="space-y-0.5">
                  <div className="text-xl font-bold text-indigo-400">100%</div>
                  <div className="text-xs text-slate-400">Cluster Routing</div>
                </div>
              </div>
            </div>

            {/* Right Branding Panel */}
            <div className="lg:col-span-5">
              <div className="relative rounded-3xl bg-slate-950 border-2 border-dashed border-slate-700/80 p-6 sm:p-8 shadow-2xl overflow-hidden group">
                <div className="absolute top-3 right-3 px-2.5 py-1 rounded-md bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-400 uppercase tracking-widest flex items-center space-x-1.5">
                  <ImageIcon className="w-3 h-3 text-emerald-400" />
                  <span>BRANDING ASSET</span>
                </div>

                <div className="space-y-6 text-center pt-4">
                  <div className="w-20 h-20 mx-auto rounded-3xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-inner group-hover:scale-105 transition-transform">
                    <ShieldCheck className="w-10 h-10" />
                  </div>

                  <div className="space-y-1.5">
                    <div className="text-xs font-bold uppercase tracking-widest text-emerald-400">
                      Alkhidmat Foundation
                    </div>
                    <h3 className="text-xl font-bold text-white">
                      Orphan Family Support Program
                    </h3>
                    <p className="text-xs text-slate-400 max-w-sm mx-auto">
                      Official Document Intake &amp; Field Verification System for Child Education &amp; Monthly Stipend Sponsorship.
                    </p>
                  </div>

                  <div className="p-3 bg-slate-900/90 rounded-2xl border border-slate-800 text-[11px] text-slate-400 text-left space-y-1">
                    <div className="flex items-center space-x-1.5 text-slate-300 font-semibold">
                      <ImageIcon className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Placeholder Slot Note:</span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-normal">
                      The official Alkhidmat high-resolution logo and photo banner will be supplied separately for this designated container.
                    </p>
                  </div>

                  <div className="flex items-center justify-center gap-2 flex-wrap">
                    {['Multan', 'Rawalpindi', 'Lahore'].map((city) => (
                      <span
                        key={city}
                        className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-slate-300"
                      >
                        {city}
                      </span>
                    ))}
                    <span className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-emerald-400">
                      + All Clusters
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Public Service Pathways ────────────────────────────────────────── */}
      <section className="py-14 bg-slate-950/60 border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="text-center max-w-2xl mx-auto space-y-2">
            <h2 className="text-2xl sm:text-3xl font-bold text-white">
              Public Service Pathways
            </h2>
            <p className="text-xs sm:text-sm text-slate-400">
              Select your role to access your dedicated portal with strict role isolation.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Orphan Family Card */}
            <div className="rounded-3xl bg-slate-900/80 border border-slate-800 p-6 sm:p-8 space-y-6 hover:border-emerald-500/50 transition-all flex flex-col justify-between">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center">
                    <Users className="w-7 h-7" />
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800 uppercase">
                    Family Portal
                  </span>
                </div>

                <div className="space-y-1">
                  <h3 className="text-xl font-bold text-white">
                    I'm an Orphan Family (Mother / Guardian)
                  </h3>
                  <p className="text-xs font-urdu text-emerald-300" dir="rtl">
                    یتیم بچے کی والدہ یا قانونی سرپرست کا پورٹل
                  </p>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">
                  Mothers or legal guardians can track their case verification status in real time. Family accounts are registered by your nearest Alkhidmat Field Support Officer.
                </p>

                <ul className="space-y-2 text-xs text-slate-300">
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Live case status tracking (Pending / Flagged / Verified)</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Document checklist uploaded by your Field Support Officer</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Automatic region-based FSO assignment</span>
                  </li>
                </ul>
              </div>

              <div className="pt-4 border-t border-slate-800">
                <button
                  onClick={() => onOpenAuth()}
                  className="w-full py-2.5 px-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs transition-colors flex items-center justify-center space-x-1.5 cursor-pointer"
                >
                  <span>Family Sign In</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
                <p className="mt-3 text-[11px] text-slate-500 text-center leading-relaxed">
                  New families are registered in person by an Alkhidmat Field Support Officer.
                </p>
              </div>
            </div>

            {/* Alkhidmat Official Card */}
            <div className="rounded-3xl bg-slate-900/80 border border-slate-800 p-6 sm:p-8 space-y-6 hover:border-indigo-500/50 transition-all flex flex-col justify-between">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
                    <ShieldCheck className="w-7 h-7" />
                  </div>
                  <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-950 text-indigo-300 border border-indigo-800 uppercase">
                    Official Roster
                  </span>
                </div>

                <div className="space-y-1">
                  <h3 className="text-xl font-bold text-white">
                    I'm an Alkhidmat Official (FSO)
                  </h3>
                  <p className="text-xs font-urdu text-indigo-300" dir="rtl">
                    الخدمت فیلڈ سپورٹ آفیسر (FSO) پورٹل
                  </p>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">
                  Field Support Officers sign in to manage assigned regional cases, inspect scanned documents against program standards, and submit field verification reports.
                </p>

                <ul className="space-y-2 text-xs text-slate-300">
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span>Regional case verification queue &amp; cluster workload</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span>Side-by-side scan inspection &amp; discrepancy cross-checking</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-indigo-400 shrink-0" />
                    <span>Assisted intake mode for remote family visits</span>
                  </li>
                </ul>
              </div>

              <div className="pt-4 border-t border-slate-800">
                <button
                  onClick={() => onOpenAuth()}
                  className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-colors flex items-center justify-center space-x-1.5 cursor-pointer"
                >
                  <span>Official Sign In (FSO)</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="mt-auto bg-slate-950 text-slate-400 text-xs py-8 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <BrandLogo size="sm" dark showWordmark={false} />
            <div>
              <span className="font-bold text-slate-200">
                CaseFill-AI &bull; Alkhidmat Family Support Program
              </span>
              <p className="text-[11px] text-slate-500">
                Orphan Family Support Program (OFSP) 2026. Certified Intake &amp; Field Verification Platform.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-4 text-[11px] text-slate-400">
            <span>National CNIC Verified</span>
            <span>&bull;</span>
            <span>Form-B CRC OCR</span>
            <span>&bull;</span>
            <span className="flex items-center space-x-1">
              <Lock className="w-3 h-3" />
              <span>Qwen-VL Powered</span>
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
};
