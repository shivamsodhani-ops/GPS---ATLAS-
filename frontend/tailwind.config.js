/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        atlas: {
          50: "#f0f7f4",
          100: "#dbeee4",
          200: "#b8ddca",
          300: "#8bc5a9",
          400: "#5aa683",
          500: "#398a67",
          600: "#297052",
          700: "#215a43",
          800: "#1c4837",
          900: "#183c2f",
          950: "#0b2119",
        },
        ink: {
          900: "#0f1720",
          800: "#1a2532",
          700: "#28394a",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(15, 23, 32, 0.06), 0 1px 3px 0 rgba(15, 23, 32, 0.08)",
      },
    },
  },
  plugins: [],
};
