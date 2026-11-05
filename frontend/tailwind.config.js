/** Escala completa ligada a um par de tokens (cor sólida + fundo suave).
 *  As telas usam 200–600 como cor de TEXTO (text-emerald-300, text-red-400) e
 *  50/100 e 700–950 como FUNDO (bg-red-950, bg-emerald-900). Mapeando nessa
 *  divisão, qualquer shade já escrito nas telas cai num valor do tema e
 *  inverte junto com ele. */
function escala(cor, suave) {
  const c = `rgb(var(--c-${cor}) / <alpha-value>)`
  const s = `rgb(var(--c-${suave}) / <alpha-value>)`
  return { 50: s, 100: s, 200: c, 300: c, 400: c, 500: c, 600: c, 700: s, 800: s, 900: s, 950: s, DEFAULT: c }
}

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-sans)'],
        display: ['var(--font-display)'],
      },
      // Raio do canvas aprovado ("Cantos"): cartão 22 px, campo/botão 12 px,
      // painel interno 14–18 px. Redefinir a escala aqui leva o raio novo
      // para os ~300 usos de rounded-* sem reescrever as telas.
      borderRadius: {
        none: '0',
        sm: '8px',
        DEFAULT: '10px',
        md: '12px',
        lg: '12px',
        xl: '16px',
        '2xl': '22px',
        '3xl': '26px',
        full: '9999px',
      },
      // Cores semânticas ligadas às variáveis de tema do index.css.
      // Trocar data-theme no <html> troca todas de uma vez.
      colors: {
        // Nomes do brief
        canvas: 'var(--canvas)',
        card: 'var(--card)',
        raised: 'var(--raised)',
        sunken: 'var(--sunken)',
        'border-subtle': 'var(--border-subtle)',
        'border-strong': 'var(--border-strong)',
        royal: {
          DEFAULT: 'var(--royal)',
          hover: 'var(--royal-hover)',
          soft: 'var(--royal-soft)',
        },
        deep: 'var(--deep)',
        'panel-ink': 'var(--panel-ink)',
        'panel-2': 'var(--panel-2)',
        'on-brand': 'var(--on-brand)',
        'accent-text': 'var(--accent-text)',
        success: 'var(--success)',
        warning: 'var(--warning)',
        danger: 'var(--danger)',
        // Nomes já usados pelas telas
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
        // Famílias do Tailwind ligadas aos tokens semânticos do tema.
        emerald: escala('success', 'success-soft'),
        green:   escala('success', 'success-soft'),
        teal:    escala('success', 'success-soft'),
        lime:    escala('success', 'success-soft'),
        red:     escala('danger', 'danger-soft'),
        rose:    escala('danger', 'danger-soft'),
        blue:    escala('royal', 'royal-soft'),
        sky:     escala('royal', 'royal-soft'),
        cyan:    escala('royal', 'royal-soft'),
        indigo:  escala('royal', 'royal-soft'),
        violet:  escala('royal', 'royal-soft'),
        purple:  escala('royal', 'royal-soft'),
        fuchsia: escala('royal', 'royal-soft'),
        pink:    escala('danger', 'danger-soft'),
        amber:   escala('warning', 'warning-soft'),
        yellow:  escala('warning', 'warning-soft'),
        orange:  escala('warning', 'warning-soft'),
        slate:   escala('neutral', 'neutral-soft'),
        gray:    escala('neutral', 'neutral-soft'),
        zinc:    escala('neutral', 'neutral-soft'),
        neutral: escala('neutral', 'neutral-soft'),
        stone:   escala('neutral', 'neutral-soft'),
      },
    },
  },
  plugins: [],
}
