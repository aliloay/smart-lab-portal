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
          950: '#0d1a2e',
          900: '#12213a',   // page
          850: '#172841',
          800: '#1b2e4b',   // card
          750: '#213656',
          700: '#273e62',   // raised / hover
          600: '#33507a',   // borders
          500: '#41618f',
          400: '#5776a3',
          300: '#7593bd',
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
        // Glass: a faint top highlight, then a soft shadow for depth.
        card: '0 1px 0 0 rgba(255,255,255,0.06) inset, 0 12px 32px -18px rgba(2,6,23,0.9)',
        lift: '0 1px 0 0 rgba(255,255,255,0.08) inset, 0 20px 40px -22px rgba(2,6,23,0.95)',
        // Glow is for a few important states only - kept faint.
        glow: '0 0 0 1px rgba(56,189,248,0.30), 0 0 22px -10px rgba(56,189,248,0.40)',
        'glow-ok': '0 0 0 1px rgba(16,185,129,0.30), 0 0 22px -12px rgba(16,185,129,0.40)',
        'glow-accent': '0 0 16px -6px rgba(14,165,233,0.45)',
      },
      backgroundImage: {
        'grid-fine':
          'linear-gradient(rgba(148,184,226,0.06) 1px, transparent 1px),' +
          'linear-gradient(90deg, rgba(148,184,226,0.06) 1px, transparent 1px)',
        'grid-major':
          'linear-gradient(rgba(125,211,252,0.07) 1px, transparent 1px),' +
          'linear-gradient(90deg, rgba(125,211,252,0.07) 1px, transparent 1px)',
        sheen: 'linear-gradient(180deg, rgba(56,189,248,0.08) 0%, transparent 55%)',
        // Very faint circuit traces for the page ground.
        circuit: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='280' height='280' fill='none' stroke='%237dd3fc' stroke-width='1'%3E%3Cpath d='M0 70h60l20 20h60M140 90v50l30 30h110M40 0v40l30 30M200 0v60l-20 20M0 210h90l30-30h40M120 280v-60l20-20h40l30 30h70M230 120v40'/%3E%3Cg fill='%237dd3fc' stroke='none'%3E%3Ccircle cx='140' cy='90' r='2.5'/%3E%3Ccircle cx='170' cy='170' r='2.5'/%3E%3Ccircle cx='70' cy='70' r='2.5'/%3E%3Ccircle cx='160' cy='180' r='2.5'/%3E%3Ccircle cx='230' cy='160' r='2.5'/%3E%3C/g%3E%3C/svg%3E\")",
      },
      backgroundSize: { 'grid-fine': '28px 28px', 'grid-major': '140px 140px', circuit: '280px 280px' },
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
