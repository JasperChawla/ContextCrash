/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      colors: {
        bg: '#09090B',
        surface: '#18181B',
        border: '#27272A',
        primary: '#3274D9',
        error: '#F87171',
        warning: '#FBBF24',
        success: '#34D399',
        muted: '#71717A',
      },
      borderRadius: {
        DEFAULT: '4px',
        sm: '2px',
        md: '4px',
        lg: '8px',
      },
    },
  },
  plugins: [],
}
