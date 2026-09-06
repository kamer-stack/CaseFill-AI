import React from 'react';

/**
 * Consistent Alkhidmat brand mark used across every screen
 * (landing page, app header, auth + help modals).
 *
 * Brand palette: emerald green (primary), gold (accent ring),
 * near-navy surfaces. Purely presentational — no data logic.
 */
export const BrandLogo: React.FC<{
  size?: 'sm' | 'md' | 'lg';
  dark?: boolean; // renders on a dark (navy) surface
  showWordmark?: boolean;
  isDualLanguage?: boolean;
  tagline?: string;
}> = ({
  size = 'md',
  dark = true,
  showWordmark = true,
  isDualLanguage = false,
  tagline,
}) => {
  const mark = size === 'sm' ? 'w-8 h-8 text-xs' : size === 'lg' ? 'w-12 h-12 text-lg' : 'w-9 h-9 text-sm';
  const title = size === 'sm' ? 'text-sm' : size === 'lg' ? 'text-lg' : 'text-base';

  const subtitle =
    tagline ??
    (isDualLanguage
      ? 'الخدمت فاؤنڈیشن • کفالت یتامیٰ پروگرام'
      : 'Alkhidmat Foundation • Orphan Family Support Program');

  return (
    <div className="flex items-center space-x-3">
      {/* Logo mark: emerald gradient square, gold ring, white monogram */}
      <div
        className={`${mark} rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-600 text-white flex items-center justify-center font-black tracking-tight brand-gold-ring shrink-0`}
        aria-label="CaseFill-AI logo"
      >
        CF
      </div>

      {showWordmark && (
        <div className="leading-tight">
          <div className="flex items-center space-x-2">
            <span className={`${title} font-extrabold ${dark ? 'text-white' : 'text-slate-900'} tracking-tight`}>
              CaseFill-AI
            </span>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
                dark
                  ? 'bg-amber-400/10 text-amber-300 border-amber-400/40'
                  : 'bg-amber-50 text-amber-700 border-amber-300'
              }`}
            >
              OFSP
            </span>
          </div>
          <p className={`text-[11px] ${dark ? 'text-slate-400' : 'text-slate-500'} truncate max-w-[260px]`}>
            {subtitle}
          </p>
        </div>
      )}
    </div>
  );
};
