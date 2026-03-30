/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Karla', 'sans-serif'],
        heading: ['Petrona', 'serif'],
      },
      colors: {
        primary: '#4ac6d6',
      },
    },
  },
  plugins: [],
}
