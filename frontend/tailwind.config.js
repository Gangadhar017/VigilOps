/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Theme tokens are CSS variables defined in src/index.css (dark + light).
        canvas: token('canvas'),
        surface: token('surface'),
        raised: token('raised'),
        line: token('line'),
        content: token('content'),
        muted: token('muted'),
        // "brand" is the accent as it can be read on a surface (text, borders, focus);
        // "accent" is the vivid fill, always used with "accent-ink" text on top.
        brand: { DEFAULT: token('brand'), strong: token('brand-strong'), soft: token('brand-soft') },
        accent: { DEFAULT: token('accent'), ink: token('accent-ink') },
        // The navigation chrome keeps its dark colours in both themes.
        chrome: {
          DEFAULT: token('chrome'),
          raised: token('chrome-raised'),
          line: token('chrome-line'),
          text: token('chrome-text'),
          muted: token('chrome-muted'),
        },
        ok: token('ok'),
        warn: token('warn'),
        danger: token('danger'),
        info: token('info'),
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        // Identifiers and figures: slashed zero so 0 and O cannot be confused.
        mono: [
          ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Cascadia Code', 'Consolas', 'Liberation Mono', 'monospace'],
          { fontFeatureSettings: '"zero"' },
        ],
      },
      boxShadow: {
        card: '0 1px 0 rgb(0 0 0 / 0.03)',
        pop: '0 18px 48px -12px rgb(0 0 0 / 0.45), 0 2px 6px rgb(0 0 0 / 0.18)',
      },
    },
  },
  plugins: [],
};
