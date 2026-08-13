/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'Noto Sans TC', 'sans-serif'],
        display: ['Outfit', 'Noto Sans TC', 'sans-serif'],
      },
      colors: {
        ricoh: {
          red: '#D11A2A',
          hoverRed: '#B01220',
          darkBg: '#0F172A',
          panelBg: '#1E293B',
        },
      },
    },
  },
  plugins: [],
};
