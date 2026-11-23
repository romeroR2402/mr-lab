/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/renderer/**/*.{ts,tsx,html}"],
  theme: {
    extend: {
      colors: {
        lab: {
          bg: "#070b10",
          panel: "#0d141c",
          panel2: "#111b26",
          line: "#1c2a38",
          text: "#d6e2ee",
          mute: "#7d8fa3",
          accent: "#22d3ee",
        },
      },
      fontFamily: {
        sans: ["Segoe UI Variable", "Segoe UI", "Inter", "system-ui", "sans-serif"],
        mono: ["Cascadia Mono", "Consolas", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
