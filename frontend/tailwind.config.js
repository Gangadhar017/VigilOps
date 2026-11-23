/** @type {import('tailwindcss').Config} */
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Theme tokens are CSS variables defined in src/index.css (light + dark).
        canvas: token('canvas'),
        surface: token('surface'),
        raised: token('raised'),
        line: token('line'),
        content: token('content'),
        muted: token('muted'),
        brand: { DEFAULT: token('brand'), strong: token('brand-strong'), soft: token('brand-soft') },
        ok: token('ok'),
        warn: token('warn'),
        danger: token('danger'),
        info: token('info'),
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Cascadia Code', 'Consolas', 'Liberation Mono', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgb(0 0 0 / 0.06), 0 1px 3px rgb(0 0 0 / 0.08)',
        pop: '0 12px 32px rgb(0 0 0 / 0.28)',
      },
    },
  },
  plugins: [],
};
