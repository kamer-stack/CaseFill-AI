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
  const mark = size === 'sm' ? 'w-8 h-8' : size === 'lg' ? 'w-12 h-12' : 'w-9 h-9';
  const title = size === 'sm' ? 'text-sm' : size === 'lg' ? 'text-lg' : 'text-base';

  const subtitle =
    tagline ??
    (isDualLanguage
      ? 'الخدمت فاؤنڈیشن • کفالت یتامیٰ پروگرام'
      : 'Alkhidmat Foundation • Orphan Family Support Program');

  return (
    <div className="flex items-center space-x-3 min-w-0">
      {/* Logo mark: heart + family + caring-hand icon (transparent PNG).
          Place the asset at /public/logo-icon.png — object-contain keeps
          its natural aspect ratio inside the square slot, no distortion. */}
      <img
        src="/logo-icon.png"
        alt="CaseFill-AI logo"
        className={`${mark} object-contain shrink-0`}
      />

      {showWordmark && (
        <div className="leading-tight min-w-0">
          <div className="flex items-center space-x-2">
            <span className={`${title} font-extrabold ${dark ? 'text-white' : 'text-neutral-900'} tracking-tight`}>
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
          <p className={`text-[11px] ${dark ? 'text-neutral-400' : 'text-neutral-600'} truncate max-w-[340px]`}>
            {subtitle}
          </p>
        </div>
      )}
    </div>
  );
};