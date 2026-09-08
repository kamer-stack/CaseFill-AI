/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        urdu: ['"Noto Nastaliq Urdu"', 'serif'],
        // Authenticated app shell only — the public landing page keeps
        // the default font-sans stack and is untouched by this token.
        app: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        // Design-system tokens for the authenticated FSO/Admin/Family screens
        // (see project's design.md, source of truth). Additive only — no
        // existing Tailwind color name is overridden, so nothing already
        // using slate/emerald/amber/rose/indigo classes changes appearance.
        brand: {
          DEFAULT: '#0d5c3a',
          dark: '#09432a',
          light: '#147a4e',
          surface: '#f3f8f5',
          border: '#dbe8e1',
        },
        // Background washes — soft gradients/glows used on the public
        // landing page hero. Additive; the app shell keeps using brand-surface.
        wash: {
          base: '#eaf3ee',
          end: '#d8eae0',
          mint: '#dcf3e6',
          cream: '#fef3c7',
        },
        // Landing page text tokens (light theme).
        ink: {
          heading: '#0f172a',
          body: '#475569',
          placeholder: '#94a3b8',
        },
        status: {
          match: '#0d5c3a',
          similar: '#d97706',
          mismatch: '#e11d48',
          review: '#d97706',
          'needs-review': '#ea580c',
          'different-script': '#7c3aed',
          // Form validation state (inputs) — distinct from the cross-check
          // `mismatch` token above, which flags document data conflicts.
          error: '#f43f5e',
        },
        case: {
          draft: '#a8a29e',
          pending: '#d97706',
          unassigned: '#7c3aed',
          flagged: '#e11d48',
          verified: '#0d5c3a',
          rejected: '#57534e',
        },
        neutral: {
          50: '#fafaf9',
          100: '#f4f4f3',
          200: '#e7e5e4',
          400: '#a8a29e',
          600: '#57534e',
          800: '#292524',
          900: '#1c1917',
        },
      },
    },
  },
  plugins: [],
};
