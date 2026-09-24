/** @type {import('tailwindcss').Config} */

/**
 * Design tokens.
 *
 * One rule governs the palette: colour carries meaning. `ok`, `warn` and
 * `bad` are reserved for state and never used decoratively, so a red on any
 * screen always means something is actually wrong. Everything structural is
 * built from the neutral `ink` ramp plus a single cyan accent.
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Deep navy ground, ascending to lighter surfaces and borders.
        ink: {
          950: '#05080f',
          900: '#080d17',
          800: '#0d1421',
          700: '#131c2d',
          600: '#1b273c',
          500: '#25344e',
          400: '#354765',
          300: '#4a5d7e',
        },
        // Single accent. Cyan reads as instrumentation rather than branding.
        accent: {
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
        },
        teal: { 400: '#2dd4bf', 500: '#14b8a6' },
        ok:   { DEFAULT: '#10b981', dim: '#10b98122' },
        warn: { DEFAULT: '#f59e0b', dim: '#f59e0b22' },
        bad:  { DEFAULT: '#ef4444', dim: '#ef444422' },
      },
      fontFamily: {
        sans: ['Inter var', 'Inter', 'ui-sans-serif', 'system-ui',
               '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas',
               'Liberation Mono', 'monospace'],
      },
      letterSpacing: { technical: '0.14em' },
      boxShadow: {
        // Elevation is a faint light from above plus a ring, not a drop
        // shadow - drop shadows read as paper, and this is an instrument.
        card: '0 1px 0 0 rgba(255,255,255,0.04) inset, 0 8px 24px -12px rgba(0,0,0,0.8)',
        lift: '0 1px 0 0 rgba(255,255,255,0.06) inset, 0 18px 40px -18px rgba(0,0,0,0.9)',
        glow: '0 0 0 1px rgba(56,189,248,0.25), 0 0 32px -8px rgba(56,189,248,0.45)',
      },
      backgroundImage: {
        'grid-fine':
          'linear-gradient(rgba(148,163,184,0.055) 1px, transparent 1px),' +
          'linear-gradient(90deg, rgba(148,163,184,0.055) 1px, transparent 1px)',
        'sheen':
          'linear-gradient(180deg, rgba(56,189,248,0.07) 0%, transparent 55%)',
      },
      backgroundSize: { 'grid-fine': '44px 44px' },
      keyframes: {
        pulseDot: {
          '0%,100%': { opacity: '1', transform: 'scale(1)' },
          '50%':     { opacity: '.45', transform: 'scale(.86)' },
        },
        sweep: {
          '0%':   { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        riseIn: {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        breathe: {
          '0%,100%': { opacity: '.25' },
          '50%':     { opacity: '.6' },
        },
      },
      animation: {
        'pulse-dot': 'pulseDot 2.4s ease-in-out infinite',
        'sweep': 'sweep 2.2s ease-in-out infinite',
        'rise-in': 'riseIn .28s ease-out both',
        'breathe': 'breathe 6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
