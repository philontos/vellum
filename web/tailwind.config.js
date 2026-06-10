/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Editorial Paper palette — warm, ink, terracotta
        paper: "#FAF7F0",
        "paper-raised": "#F4EFE4",
        ink: "#221F1A",
        "ink-soft": "#3A352E",
        muted: "#8C8273",
        line: "#E7E0D3",
        card: "#FFFFFF",
        "card-line": "#ECE5D8",
        terracotta: "#B25A3A",
        "terracotta-ink": "#9A4A2D",
        // Harmonized status palette (muted, warm-leaning)
        status: {
          "pass-fg": "#4F6F45",
          "pass-bg": "#E9EFE1",
          "fail-fg": "#9A2D22",
          "fail-bg": "#F3E1DB",
          "warn-fg": "#8A6A1E",
          "warn-bg": "#F4ECD6",
          "info-fg": "#3A6071",
          "info-bg": "#E2EAEE",
          "neutral-fg": "#8C8273",
          "neutral-bg": "#F0EBDF",
        },
      },
      fontFamily: {
        serif: ["Newsreader", "Songti SC", "Noto Serif SC", "Georgia", "serif"],
        sans: ["Inter", "PingFang SC", "Noto Sans SC", "system-ui", "sans-serif"],
      },
      borderRadius: {
        bubble: "15px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(34,28,20,.06)",
        raised: "0 1px 2px rgba(34,28,20,.06), 0 4px 14px rgba(34,28,20,.06)",
        float: "0 1px 2px rgba(34,28,20,.06), 0 14px 40px rgba(34,28,20,.14)",
      },
    },
  },
  plugins: [],
};
