import React from 'react';
import {
  Sparkles,
  ArrowRight,
  FileStack,
  Clock,
  ShieldCheck,
  ChevronDown,
} from 'lucide-react';

interface LandingHeroProps {
  onOpenAuth: () => void;
  onScrollToFaq: () => void;
  isDualLanguage: boolean;
}

interface StatCard {
  value: string;
  label: string;
  sublabel?: string;
  icon: typeof FileStack;
  accent: string;
  iconBg: string;
}

const STAT_CARDS: StatCard[] = [
  {
    value: '8 Documents',
    label: 'Civil Registry OCR',
    icon: FileStack,
    accent: 'text-ink-heading',
    iconBg: 'bg-wash-mint border-brand-light/40 text-brand',
  },
  {
    value: '<3 Mins',
    label: 'Average Intake Time',
    icon: Clock,
    accent: 'text-brand',
    iconBg: 'bg-wash-mint border-brand-light/40 text-brand',
  },
  {
    value: '100%',
    label: 'Human Review',
    sublabel: 'FSO Audit Trail',
    icon: ShieldCheck,
    accent: 'text-amber-700',
    iconBg: 'bg-wash-cream border-amber-300/60 text-amber-700',
  },
];

export const LandingHero: React.FC<LandingHeroProps> = ({
  onOpenAuth,
  onScrollToFaq,
  isDualLanguage,
}) => {
  return (
    <section className="relative pt-12 pb-10 md:pt-16 md:pb-14 border-b border-brand-border overflow-hidden bg-gradient-to-b from-wash-base to-wash-end">
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[640px] h-[320px] bg-wash-mint/70 blur-[120px] pointer-events-none rounded-full" />
      <div className="absolute top-1/3 right-0 w-[420px] h-[280px] bg-wash-cream/60 blur-[100px] pointer-events-none rounded-full" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 space-y-10 md:space-y-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-center">
          {/* Copy + CTAs */}
          <div className="lg:col-span-6 xl:col-span-5 space-y-6 text-left">
            <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-full bg-white border border-brand-border text-brand-dark text-xs font-semibold shadow-sm">
              <Sparkles className="w-3.5 h-3.5 text-brand" />
              <span>AI-Assisted Orphan Case Intake for FSOs</span>
            </div>

            <div className="space-y-4">
              <h1 className="text-3xl sm:text-4xl lg:text-[2.75rem] font-extrabold text-ink-heading tracking-tight leading-[1.12]">
                Faster Document Intake.
                <span className="block text-brand mt-1">Every Field FSO-Verified.</span>
              </h1>
              <p className="text-base sm:text-lg text-ink-body font-normal leading-relaxed max-w-xl">
                CaseFill-AI extracts data from 8 sponsorship documents so Field Support Officers can review,
                correct, and confirm every field before a case is finalized — cutting manual intake from
                10–15 minutes to under 3.
              </p>
              {isDualLanguage && (
                <p className="text-sm sm:text-base font-urdu text-brand-dark font-medium leading-relaxed max-w-xl" dir="rtl">
                  کیس فل اے آئی 8 دستاویزات سے ڈیٹا نکالتا ہے تاکہ فیلڈ سپورٹ آفیسر ہر فیلڈ کی تصدیق
                  اور درستگی خود کر سکیں — AI کا فیصلہ حتمی نہیں ہوتا۔
                </p>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-3.5 pt-1">
              <button
                onClick={() => onOpenAuth()}
                className="px-6 py-3.5 rounded-xl bg-brand hover:bg-brand-dark text-white font-bold text-sm shadow-lg shadow-brand/20 flex items-center space-x-2 transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
              >
                <span>{isDualLanguage ? 'FSO پورٹل میں لاگ ان' : 'Sign In to FSO Portal'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
              <button
                onClick={onScrollToFaq}
                className="px-6 py-3.5 rounded-xl bg-white hover:bg-brand-surface text-ink-heading font-bold text-sm border border-brand-border hover:border-brand-light flex items-center space-x-2 transition-colors cursor-pointer"
              >
                <span>{isDualLanguage ? 'اکثر پوچھے گئے سوالات' : 'View FAQ'}</span>
                <ChevronDown className="w-4 h-4 text-ink-placeholder" />
              </button>
            </div>
          </div>

          {/* Hero image */}
          <div className="lg:col-span-6 xl:col-span-7">
            <div className="relative rounded-3xl overflow-hidden border border-brand-border shadow-2xl shadow-brand/10 bg-white aspect-[4/3] sm:aspect-[16/11] lg:aspect-[5/4]">
              <img
                src="/hero-photo.jpg"
                alt="Orphan celebrating World Health Day"
                className="w-full h-full object-cover"
                onError={(e) => {
                  // Missing/broken file: hide the <img> and reveal the placeholder below instead
                  e.currentTarget.style.display = 'none';
                  const placeholder = e.currentTarget.nextElementSibling as HTMLElement | null;
                  if (placeholder) placeholder.style.display = 'flex';
                }}
              />
              <div
                className="hidden w-full h-full items-center justify-center flex-col gap-3 bg-gradient-to-br from-wash-base to-wash-mint text-ink-placeholder"
              >
                <Sparkles className="w-10 h-10 text-brand/60" />
                <p className="text-xs text-ink-placeholder px-6 text-center">
                  Hero image not found — add hero-photo.jpg to /public
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Stat highlight cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 md:gap-5">
          {STAT_CARDS.map(({ value, label, sublabel, icon: Icon, accent, iconBg }) => (
            <div
              key={value}
              className="rounded-2xl bg-white border border-brand-border p-5 sm:p-6 flex items-start gap-4 hover:border-brand-light/60 transition-colors shadow-sm"
            >
              <div className={`shrink-0 w-11 h-11 rounded-xl border flex items-center justify-center ${iconBg}`}>
                <Icon className="w-5 h-5" />
              </div>
              <div className="space-y-0.5 min-w-0">
                <div className={`text-2xl sm:text-[1.65rem] font-extrabold tracking-tight ${accent}`}>
                  {value}
                </div>
                <div className="text-sm text-ink-body font-medium">{label}</div>
                {sublabel && <div className="text-xs text-ink-placeholder">{sublabel}</div>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
