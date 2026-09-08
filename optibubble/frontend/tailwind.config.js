/** Ledger design language (v5) — tokens map to CSS vars so the light/dark
 *  theme swaps by toggling one class on <html>. */
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
        brand: ["OPTIBubble", "sans-serif"],
      },
      borderRadius: { DEFAULT: "10px", card: "14px" },
      boxShadow: {
        focus: "0 0 0 2px var(--bg0), 0 0 0 4px var(--brand)",
        card: "var(--shadow-card)",
        pop: "var(--shadow-pop)",
        brand: "0 0 0 1px rgba(47,111,237,.22), 0 8px 30px rgba(47,111,237,.16)",
      },
      transitionTimingFunction: { spring: "cubic-bezier(.2,.9,.3,1.15)" },
    },
  },
  plugins: [],
};
