import React from 'react';
import { BadgeCheck } from 'lucide-react';

/**
 * "Reviewed by [FSO name] on [date]" note shown on verified cases.
 * Presentational only — reads existing case fields
 * (verified_by_fso_name / verified_at).
 */
export const ReviewedByNote: React.FC<{
  name?: string;
  date?: string;
  isDualLanguage?: boolean;
}> = ({ name, date, isDualLanguage = false }) => {
  if (!name && !date) return null;

  const formatted = date
    ? new Date(date).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : null;

  let text: string | null = null;
  if (name && formatted) {
    text = isDualLanguage
      ? `جائزہ لیا: ${name} — ${formatted}`
      : `Reviewed by ${name} on ${formatted}`;
  } else if (name) {
    text = isDualLanguage ? `جائزہ لیا: ${name}` : `Reviewed by ${name}`;
  } else if (formatted) {
    text = isDualLanguage ? `تصدیق کی تاریخ: ${formatted}` : `Verified on ${formatted}`;
  }

  if (!text) return null;

  return (
    <div className="inline-flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-full pl-1.5 pr-3.5 py-1.5 w-fit">
      <span className="w-6 h-6 rounded-full bg-emerald-100 border border-emerald-200 flex items-center justify-center shrink-0">
        <BadgeCheck className="w-3.5 h-3.5 text-emerald-600" />
      </span>
      <span className="text-xs font-semibold text-emerald-800">{text}</span>
    </div>
  );
};
