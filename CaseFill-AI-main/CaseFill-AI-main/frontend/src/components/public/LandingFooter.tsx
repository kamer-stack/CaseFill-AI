import React from 'react';
import { BrandLogo } from '../shared/BrandLogo';
import { Globe, Lock, Phone, Mail } from 'lucide-react';

interface LandingFooterProps {
  isDualLanguage: boolean;
  setIsDualLanguage: (val: boolean) => void;
  onScrollToFaq: () => void;
  onOpenAuth: () => void;
}

export const LandingFooter: React.FC<LandingFooterProps> = ({
  isDualLanguage,
  setIsDualLanguage,
  onScrollToFaq,
  onOpenAuth,
}) => {
  return (
    <footer className="bg-slate-50 text-slate-600 text-sm border-t border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-14">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 lg:gap-8">
          {/* Logo & description */}
          <div className="space-y-4 sm:col-span-2 lg:col-span-1 min-w-0">
            <BrandLogo size="md" dark={false} isDualLanguage={isDualLanguage} />
            <p className="text-xs text-slate-500 leading-relaxed max-w-xs">
              AI-assisted document intake for Alkhidmat Field Support Officers. Every case is
              human-reviewed before verification — the AI never has final say.
            </p>
            <div className="flex items-center flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-400">
              <span className="flex items-center gap-1">
                <Lock className="w-3 h-3" />
                Qwen-VL Powered
              </span>
              <span>&bull;</span>
              <span>OFSP 2026</span>
            </div>
          </div>

          {/* Program Navigation */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Program Navigation
            </h3>
            <ul className="space-y-2 text-xs">
              <li>
                <button
                  type="button"
                  onClick={onScrollToFaq}
                  className="text-slate-600 hover:text-emerald-700 transition-colors cursor-pointer"
                >
                  Frequently Asked Questions
                </button>
              </li>
              <li>
                <button
                  type="button"
                  onClick={onOpenAuth}
                  className="text-slate-600 hover:text-emerald-700 transition-colors cursor-pointer"
                >
                  FSO Portal Sign In
                </button>
              </li>
              <li>
                <span className="text-slate-500">8-Document Intake Checklist</span>
              </li>
              <li>
                <span className="text-slate-500">Orphan Family Support Program (OFSP)</span>
              </li>
            </ul>
          </div>

          {/* Field Assistance & Helpline */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Field Assistance &amp; Helpline
            </h3>
            <ul className="space-y-2.5 text-xs">
              <li className="flex items-start gap-2">
                <Phone className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <p className="text-slate-700 font-medium">Regional Cluster Office</p>
                  <p className="text-slate-500">Contact your assigned cluster admin for FSO account issues.</p>
                </div>
              </li>
              <li className="flex items-start gap-2">
                <Mail className="w-3.5 h-3.5 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <a
                    href="mailto:fso-support@alkhidmat.org"
                    className="text-emerald-700 hover:text-emerald-800 font-medium transition-colors"
                  >
                    fso-support@alkhidmat.org
                  </a>
                  <p className="text-slate-500">Document intake &amp; workflow support</p>
                </div>
              </li>
            </ul>
          </div>

          {/* Language & Accessibility */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
              Language &amp; Accessibility
            </h3>
            <ul className="space-y-2.5 text-xs text-slate-500">
              <li>
                <button
                  type="button"
                  onClick={() => setIsDualLanguage(!isDualLanguage)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-700 hover:border-emerald-300 hover:text-emerald-800 transition-colors cursor-pointer"
                >
                  <Globe className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="font-semibold">
                    {isDualLanguage ? 'Switch to English only' : 'Enable Urdu / English'}
                  </span>
                </button>
              </li>
              <li>Keyboard-accessible FAQ accordion</li>
              <li>High-contrast emerald &amp; navy brand palette</li>
              <li>Bilingual labels available when Urdu mode is enabled</li>
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-slate-400">
          <span>
            &copy; {new Date().getFullYear()} CaseFill-AI &bull; Alkhidmat Family Support Program
          </span>
          <span>National CNIC Verified &bull; Form-B CRC OCR</span>
        </div>
      </div>
    </footer>
  );
};
