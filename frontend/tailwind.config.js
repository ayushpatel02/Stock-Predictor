/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        buy: '#16a34a',
        sell: '#dc2626',
        hold: '#ca8a04',
      },
    },
  },
  plugins: [],
}
