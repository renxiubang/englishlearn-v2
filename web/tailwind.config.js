/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        blue: '#4A90E2',
        orange: '#FF6B35',
      },
    },
  },
  plugins: [],
}
