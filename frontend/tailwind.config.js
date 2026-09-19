/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      // Cores semânticas ligadas às variáveis de tema do index.css.
      // Trocar data-theme no <html> troca todas de uma vez.
      colors: {
        brand: {
          DEFAULT: 'var(--brand)',
          ink: 'var(--brand-ink)',
        },
        surface: {
          DEFAULT: 'var(--surface)',
          2: 'var(--surface-2)',
        },
        raise: {
          1: 'var(--raise-1)',
          2: 'var(--raise-2)',
          3: 'var(--raise-3)',
        },
        line: {
          DEFAULT: 'var(--line)',
          2: 'var(--line-2)',
        },
        ink: {
          DEFAULT: 'var(--ink)',
          2: 'var(--ink-2)',
          3: 'var(--ink-3)',
          4: 'var(--ink-4)',
        },
        // Tons de acento usados como texto claro (200/300/400) ou fundo
        // escuro (900/950). Ligados a variáveis para inverterem no tema claro.
        emerald: {
          200: 'rgb(var(--c-emerald-200) / <alpha-value>)',
          300: 'rgb(var(--c-emerald-300) / <alpha-value>)',
          400: 'rgb(var(--c-emerald-400) / <alpha-value>)',
          900: 'rgb(var(--c-emerald-900) / <alpha-value>)',
          950: 'rgb(var(--c-emerald-950) / <alpha-value>)',
        },
        red: {
          200: 'rgb(var(--c-red-200) / <alpha-value>)',
          300: 'rgb(var(--c-red-300) / <alpha-value>)',
          400: 'rgb(var(--c-red-400) / <alpha-value>)',
          900: 'rgb(var(--c-red-900) / <alpha-value>)',
          950: 'rgb(var(--c-red-950) / <alpha-value>)',
        },
        blue: {
          200: 'rgb(var(--c-blue-200) / <alpha-value>)',
          300: 'rgb(var(--c-blue-300) / <alpha-value>)',
          400: 'rgb(var(--c-blue-400) / <alpha-value>)',
          900: 'rgb(var(--c-blue-900) / <alpha-value>)',
          950: 'rgb(var(--c-blue-950) / <alpha-value>)',
        },
        amber: {
          200: 'rgb(var(--c-amber-200) / <alpha-value>)',
          300: 'rgb(var(--c-amber-300) / <alpha-value>)',
          400: 'rgb(var(--c-amber-400) / <alpha-value>)',
          900: 'rgb(var(--c-amber-900) / <alpha-value>)',
          950: 'rgb(var(--c-amber-950) / <alpha-value>)',
        },
        violet: {
          200: 'rgb(var(--c-violet-200) / <alpha-value>)',
          300: 'rgb(var(--c-violet-300) / <alpha-value>)',
          400: 'rgb(var(--c-violet-400) / <alpha-value>)',
        },
        indigo: {
          200: 'rgb(var(--c-indigo-200) / <alpha-value>)',
          300: 'rgb(var(--c-indigo-300) / <alpha-value>)',
          400: 'rgb(var(--c-indigo-400) / <alpha-value>)',
        },
        rose: {
          300: 'rgb(var(--c-rose-300) / <alpha-value>)',
          400: 'rgb(var(--c-rose-400) / <alpha-value>)',
        },
        orange: {
          400: 'rgb(var(--c-orange-400) / <alpha-value>)',
        },
        page: 'var(--bg)',
      },
      borderColor: {
        DEFAULT: 'var(--line)',
      },
    },
  },
  plugins: [],
}
