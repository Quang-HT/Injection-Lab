/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Rajdhani", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        chrome: {
          950: "#060816",
          900: "#0a1021",
          850: "#0f1730",
          800: "#111f3f",
          700: "#1a2a52",
        },
        signal: {
          500: "#37f2ff",
          400: "#5cf6d7",
          300: "#86f4a2",
        },
        threat: {
          500: "#ff875d",
          400: "#ffb85f",
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(55, 242, 255, 0.12), 0 24px 80px rgba(6, 12, 28, 0.75)",
      },
      keyframes: {
        pulseFlag: {
          "0%, 100%": { transform: "scale(1)", opacity: "0.9" },
          "50%": { transform: "scale(1.02)", opacity: "1" },
        },
        shimmer: {
          "0%": { transform: "translateX(-120%)" },
          "100%": { transform: "translateX(120%)" },
        },
      },
      animation: {
        "flag-pulse": "pulseFlag 1.6s ease-in-out infinite",
        shimmer: "shimmer 1.8s linear infinite",
      },
    },
  },
  plugins: [],
};
