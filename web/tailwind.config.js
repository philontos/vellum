/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Ember Noir — deep espresso ground, sienna accent, gold detail.
        base: "#110D09",
        surface: "#18120C",
        well: "#0F0C08",
        ink: "#EFE6D7",
        "ink-soft": "#C4B8A6",
        muted: "#897E6F",
        line: "#281F16",
        accent: "#D0663F",
        "accent-ink": "#E07A52",
        "accent-fg": "#160D07",
        gold: "#C6975A",
        // Functional status palette — dark-tinted, low-saturation (not the hero accent).
        status: {
          "pass-fg": "#9ABF82",
          "pass-bg": "#1B2417",
          "fail-fg": "#D98C78",
          "fail-bg": "#2A1A15",
          "warn-fg": "#D9B36A",
          "warn-bg": "#262017",
          "info-fg": "#8FB1C2",
          "info-bg": "#16212A",
          "neutral-fg": "#9A8F7E",
          "neutral-bg": "#1E1A14",
        },
      },
      fontFamily: {
        serif: ["Newsreader", "Songti SC", "Noto Serif SC", "Georgia", "serif"],
        sans: ["Inter", "PingFang SC", "Noto Sans SC", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,.4)",
        raised: "0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.45)",
        float: "0 1px 2px rgba(0,0,0,.5), 0 18px 50px rgba(0,0,0,.6)",
      },
    },
  },
  plugins: [],
};
