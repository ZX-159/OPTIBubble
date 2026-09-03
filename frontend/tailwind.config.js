/** Blueprint design language (v3) — tokens map to CSS vars so the day theme
 *  swaps by toggling one class on <html>. */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        base: "var(--bg0)", surface: "var(--bg1)", raised: "var(--bg2)",
        fill: "var(--bg3)", ink: "var(--tx)", ink2: "var(--tx2)",
        ink3: "var(--tx3)", brand: "var(--brand)", brandhi: "var(--brand-hi)",
        brandink: "var(--brand-ink)", ok: "var(--ok)", warn: "var(--warn)",
        err: "var(--err)", hair: "var(--hair)", hair2: "var(--hair2)",
        okdim: "var(--ok-dim)", warndim: "var(--warn-dim)", errdim: "var(--err-dim)",
        branddim: "var(--brand-dim)",
      },
      fontFamily: {
        sans: ["Instrument Sans", "Open Sans", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
        serif: ["Instrument Serif", "Georgia", "serif"],
      },
      borderRadius: { DEFAULT: "8px", card: "12px" },
      boxShadow: {
        focus: "0 0 0 2px var(--bg0), 0 0 0 4px var(--brand)",
        card: "inset 0 1px 0 rgba(255,255,255,.035), 0 10px 34px rgba(0,0,0,.34)",
        pop: "0 24px 70px rgba(0,0,0,.55)",
        brand: "0 0 0 1px rgba(56,225,198,.25), 0 8px 30px rgba(56,225,198,.18)",
      },
      transitionTimingFunction: { spring: "cubic-bezier(.2,.9,.3,1.15)" },
    },
  },
  plugins: [],
};
