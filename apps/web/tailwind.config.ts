import type { Config } from 'tailwindcss';
import animate from 'tailwindcss-animate';

/**
 * KEYSTONE design tokens — see docs/UI_SCHEMA.md §2.
 * Raw values live as CSS custom properties in app/globals.css; Tailwind only references them,
 * so the legacy modal stylesheet and the new regions share one source of truth.
 */
const config: Config = {
  darkMode: ['class'],
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './lib/**/*.{ts,tsx}', './hooks/**/*.{ts,tsx}'],
  theme: {
    container: { center: true, padding: '1rem' },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary: { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        popover: { DEFAULT: 'hsl(var(--popover))', foreground: 'hsl(var(--popover-foreground))' },
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
        ks: {
          abyss: 'rgb(var(--ks-abyss-rgb) / <alpha-value>)',
          chrome: 'rgb(var(--ks-chrome-rgb) / <alpha-value>)',
          raised: 'rgb(var(--ks-raised-rgb) / <alpha-value>)',
          lift: 'rgb(var(--ks-lift-rgb) / <alpha-value>)',
          line: 'var(--ks-line)',
          'line-strong': 'var(--ks-line-strong)',
          ink: 'rgb(var(--ks-ink-rgb) / <alpha-value>)',
          'ink-2': 'rgb(var(--ks-ink-2-rgb) / <alpha-value>)',
          'ink-3': 'rgb(var(--ks-ink-3-rgb) / <alpha-value>)',
          indigo: 'rgb(var(--ks-indigo-rgb) / <alpha-value>)',
          violet: 'rgb(var(--ks-violet-rgb) / <alpha-value>)',
          verified: 'rgb(var(--ks-verified-rgb) / <alpha-value>)',
          hold: 'rgb(var(--ks-hold-rgb) / <alpha-value>)',
          deny: 'rgb(var(--ks-deny-rgb) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-jetbrains)', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        // Modular scale (≈1.2) anchored at 14px body — UI_SCHEMA §2.2
        micro: ['11px', { lineHeight: '14px', letterSpacing: '0.01em' }],
        meta: ['12px', { lineHeight: '16px' }],
        body: ['13.5px', { lineHeight: '20px' }],
        lead: ['15px', { lineHeight: '22px' }],
        title: ['18px', { lineHeight: '24px', letterSpacing: '-0.01em' }],
        stage: ['34px', { lineHeight: '38px', letterSpacing: '-0.025em' }],
      },
      borderRadius: {
        frame: '6px',
        control: '8px',
        panel: '12px',
        composer: '18px',
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      spacing: {
        rail: '60px',
        panel: '280px',
        inspector: '320px',
        topbar: '52px',
      },
      transitionTimingFunction: {
        shutter: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
      },
      transitionDuration: {
        quick: '120ms',
        base: '200ms',
        settle: '320ms',
      },
      boxShadow: {
        float: '0 24px 60px -12px rgba(0,0,0,0.75), 0 0 0 1px var(--ks-line-strong)',
        frame: '0 30px 80px -20px rgba(0,0,0,0.9)',
      },
      keyframes: {
        'exposure-sweep': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        'cognition-pulse': {
          '0%, 100%': { opacity: '0.45' },
          '50%': { opacity: '1' },
        },
      },
      animation: {
        'exposure-sweep': 'exposure-sweep 1.8s cubic-bezier(0.4, 0, 0.2, 1) infinite',
        'cognition-pulse': 'cognition-pulse 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [animate],
};

export default config;
