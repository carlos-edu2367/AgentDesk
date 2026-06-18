/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          950: '#0a0a0f',
          900: '#0f1117',
          800: '#161b27',
          700: '#1e2535',
        },
      },
    },
  },
  plugins: [],
}
