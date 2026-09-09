import React, { useEffect, useRef, useState } from 'react';
import { BrandLogo } from '../shared/BrandLogo';
import { Globe } from 'lucide-react';
import { LandingHero } from './LandingHero';
import { LandingFaqSection } from './LandingFaqSection';
import { LandingFooter } from './LandingFooter';

interface LandingPageProps {
  onOpenAuth: () => void;
  isDualLanguage: boolean;
  setIsDualLanguage: (val: boolean) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onOpenAuth,
  isDualLanguage: _isDualLanguage,
  setIsDualLanguage,
}) => {
  const faqRef = useRef<HTMLElement>(null);
  const [dualLang, setDualLang] = useState(false);

  // Sync parent App state — parent initializes isDualLanguage to true.
  useEffect(() => {
    setIsDualLanguage(false);
  }, [setIsDualLanguage]);

  const toggleLanguage = () => {
    const next = !dualLang;
    setDualLang(next);
    setIsDualLanguage(next);
  };

  const scrollToFaq = () => {
    faqRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="min-h-screen flex flex-col font-sans selection:bg-brand-light selection:text-white">
      {/* Hero zone — unified brand palette (emerald + off-white) */}
      <div className="bg-brand-surface text-ink-heading">
        <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-brand-border">
          <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-2.5 sm:py-3.5 flex items-center justify-between gap-2">
            {/* Logo: compact mark (no subtitle) below sm, full wordmark + tagline at sm+ */}
            <div className="min-w-0 shrink-0">
              <div className="sm:hidden">
                <BrandLogo size="sm" dark={false} isDualLanguage={dualLang} tagline="" />
              </div>
              <div className="hidden sm:block">
                <BrandLogo size="lg" dark={false} isDualLanguage={dualLang} />
              </div>
            </div>

            <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
              <button
                onClick={toggleLanguage}
                className="px-2 sm:px-2.5 py-1.5 rounded-xl bg-brand-surface hover:bg-wash-mint border border-brand-border text-xs text-ink-body hover:text-brand-dark flex items-center gap-1 sm:gap-1.5 transition-colors cursor-pointer"
                title="Toggle English / اردو"
              >
                <Globe className="w-3.5 h-3.5 text-brand shrink-0" />
                {/* Label text hidden on mobile — icon-only toggle to save width */}
                <span className="hidden sm:inline font-semibold text-[11px]">
                  {dualLang ? 'اردو / English' : 'English'}
                </span>
              </button>

              <button
                onClick={() => onOpenAuth()}
                className="px-3 sm:px-4 py-2 rounded-xl bg-brand hover:bg-brand-dark text-white font-bold text-xs border border-brand hover:border-brand-dark transition-all cursor-pointer whitespace-nowrap"
              >
                {/* Shorter label on mobile, original full label preserved at sm+ */}
                <span className="sm:hidden">{dualLang ? 'لاگ ان' : 'Sign In'}</span>
                <span className="hidden sm:inline">{dualLang ? 'لاگ ان (Sign In)' : 'Sign In'}</span>
              </button>
            </div>
          </div>
        </header>

        <LandingHero
          onOpenAuth={onOpenAuth}
          onScrollToFaq={scrollToFaq}
          isDualLanguage={dualLang}
        />
      </div>

      {/* Content zone — FAQ + Footer */}
      <div className="flex-1 bg-white text-ink-heading">
        <LandingFaqSection
          isDualLanguage={dualLang}
          sectionRef={faqRef}
        />

        <LandingFooter
          isDualLanguage={dualLang}
          setIsDualLanguage={(val) => {
            setDualLang(val);
            setIsDualLanguage(val);
          }}
          onScrollToFaq={scrollToFaq}
          onOpenAuth={onOpenAuth}
        />
      </div>
    </div>
  );
};
