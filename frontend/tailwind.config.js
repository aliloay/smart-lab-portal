/** @type {import('tailwindcss').Config} */

/**
 * Design tokens.
 *
 * Colour carries meaning. `ok`, `warn` and `bad` are reserved for state and
 * never used decoratively, so a red anywhere always means something is wrong.
 * Structure is built from the `ink` ramp - a blue-grey navy rather than near
 * black, so cards separate from the page and text reads without strain - plus
 * a cyan/blue accent, a teal secondary, and violet used sparingly.
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#070d18',
          900: '#0b1322',   // page
          850: '#0f1a2c',
          800: '#132036',   // card
          750: '#172741',
          700: '#1c2e4a',   // raised / hover
          600: '#253a5a',   // borders
          500: '#314a70',
          400: '#46618a',
          300: '#6582ab',
        },
        accent: {
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
        },
        signal: { 300: '#67e8f9', 400: '#22d3ee', 500: '#06b6d4' },   // electric cyan
        teal: { 300: '#5eead4', 400: '#2dd4bf', 500: '#14b8a6' },
        violet: { 300: '#c4b5fd', 400: '#a78bfa', 500: '#8b5cf6' },
        ok:   { DEFAULT: '#10b981', soft: '#34d399' },
        warn: { DEFAULT: '#f59e0b', soft: '#fbbf24' },
        bad:  { DEFAULT: '#ef4444', soft: '#f87171' },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system',
               'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['"Space Grotesk"', 'Inter', 'ui-sans-serif', 'system-ui',
                  'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo',
               'Consolas', 'monospace'],
      },
      letterSpacing: { technical: '0.14em' },
      boxShadow: {
        card: '0 1px 0 0 rgba(255,255,255,0.05) inset, 0 10px 30px -14px rgba(2,6,23,0.85)',
        lift: '0 1px 0 0 rgba(255,255,255,0.07) inset, 0 22px 44px -20px rgba(2,6,23,0.95)',
        glow: '0 0 0 1px rgba(56,189,248,0.28), 0 0 36px -8px rgba(56,189,248,0.45)',
        'glow-ok': '0 0 0 1px rgba(16,185,129,0.30), 0 0 36px -10px rgba(16,185,129,0.45)',
        'glow-accent': '0 0 24px -4px rgba(14,165,233,0.65)',
      },
      backgroundImage: {
        'grid-fine':
          'linear-gradient(rgba(148,184,226,0.06) 1px, transparent 1px),' +
          'linear-gradient(90deg, rgba(148,184,226,0.06) 1px, transparent 1px)',
        'grid-major':
          'linear-gradient(rgba(125,211,252,0.07) 1px, transparent 1px),' +
          'linear-gradient(90deg, rgba(125,211,252,0.07) 1px, transparent 1px)',
        sheen: 'linear-gradient(180deg, rgba(56,189,248,0.08) 0%, transparent 55%)',
      },
      backgroundSize: { 'grid-fine': '28px 28px', 'grid-major': '140px 140px' },
      keyframes: {
        pulseDot: {
          '0%,100%': { opacity: '1', transform: 'scale(1)' },
          '50%':     { opacity: '.45', transform: 'scale(.86)' },
        },
        ping2: {
          '0%':   { transform: 'scale(1)', opacity: '.55' },
          '100%': { transform: 'scale(2.6)', opacity: '0' },
        },
        sweep: {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        pageIn: {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        breathe: {
          '0%,100%': { opacity: '.35' },
          '50%':     { opacity: '.75' },
        },
        floaty: {
          '0%,100%': { transform: 'translateY(0)' },
          '50%':     { transform: 'translateY(-8px)' },
        },
        dash: { to: { strokeDashoffset: '-40' } },
        spinSlow: { to: { transform: 'rotate(360deg)' } },
        scan: {
          '0%,100%': { transform: 'translateY(0)' },
          '50%':     { transform: 'translateY(100%)' },
        },
      },
      animation: {
        'pulse-dot': 'pulseDot 2.4s ease-in-out infinite',
        'ping-slow': 'ping2 2.4s cubic-bezier(0,0,.2,1) infinite',
        sweep: 'sweep 2.2s ease-in-out infinite',
        'page-in': 'pageIn .22s cubic-bezier(.22,1,.36,1) both',
        breathe: 'breathe 7s ease-in-out infinite',
        floaty: 'floaty 7s ease-in-out infinite',
        dash: 'dash 1.6s linear infinite',
        'spin-slow': 'spinSlow 24s linear infinite',
        scan: 'scan 3.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
