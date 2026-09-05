import React, { memo, useId, useMemo } from "react";
import { motion, useReducedMotion } from "motion/react";
import { softSpring } from "./ui";

/* ------------------------------------------------------------------ helpers
   Lightweight, theme-aware inline-SVG charts. Every colour is a CSS variable
   (--brand, --ok, --warn, --err, --tx3, --bg3, --hair…) so the same markup
   renders correctly in light AND dark without a re-render. Components are
   memoised; the browser never rebuilds them on a poll tick unless their
   data actually changed. */

const SCALE = (v, lo, hi) => (hi === lo ? 0 : (v - lo) / (hi - lo));

/* Convert a flat array into a smooth SVG path (monotone-ish). */
function smooth(points) {
  if (points.length < 2) return "";
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length; i++) {
    const [x0, y0] = [points[i - 1].x, points[i - 1].y];
    const [x1, y1] = [points[i].x, points[i].y];
    const mx = (x0 + x1) / 2;
    d += ` C ${mx} ${y0}, ${mx} ${y1}, ${x1} ${y1}`;
  }
  return d;
}

/* ---------------------------------------------------- Spark (area + line) */
export const Spark = memo(function Spark({ data = [], color = "var(--brand)",
  height = 40, fill = true, id }) {
  const uid = useId();
  const gid = `grad-${uid}`;
  const n = data.length;
  const W = 120;
  const min = Math.min(0, ...data);
  const max = Math.max(1, ...data);
  const pts = useMemo(() => data.map((v, i) => ({
    x: (i / Math.max(1, n - 1)) * W,
    y: height - 3 - SCALE(v, min, max) * (height - 6),
  })), [data, min, max, height, n]);
  const line = useMemo(() => smooth(pts), [pts]);
  if (n < 2) return null;
  const area = `${line} L ${W} ${height} L 0 ${height} Z`;
  return (
    <svg className="block w-full" viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none"
      aria-hidden="true" style={{ height }}>
      <defs>
        <linearGradient id={id || gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#${id || gid})`} />}
      <path d={line} fill="none" stroke={color} strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
});

/* ------------------------------------------------------ KR-20 radial gauge */
export const RadialGauge = memo(function RadialGauge({ value = 0, size = 120,
  stroke = 11, label = "reliability", tone }) {
  const reduced = useReducedMotion();
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.min(1, Math.max(0, value));
  const t = tone || (pct >= 0.8 ? "var(--ok)" : pct >= 0.6 ? "var(--warn)" : "var(--err)");
  return (
    <div className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}>
      <svg width={size} height={size} className="block -rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bg3)"
          strokeWidth={stroke} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={t}
          strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c}
          initial={reduced ? { strokeDashoffset: c * (1 - pct) } : { strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - pct) }}
          transition={softSpring} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <b className="tnum text-[22px] font-extrabold leading-none" style={{ color: t }}>
          {pct.toFixed(2)}</b>
        <span className="mt-0.5 text-[9px] font-extrabold uppercase tracking-[0.12em]
          text-ink3">{label}</span>
      </div>
    </div>
  );
});

/* ------------------------------------------------------- score histogram */
export const ScoreHistogram = memo(function ScoreHistogram({ scores = [], binCount = 10,
  height = 180 }) {
  const reduced = useReducedMotion();
  const wid = useMemo(() => {
    const bins = Array.from({ length: binCount }, () => 0);
    scores.forEach((s) => {
      const i = Math.min(binCount - 1, Math.max(0, Math.floor(s / (100 / binCount))));
      bins[i] += 1;
    });
    return bins;
  }, [scores, binCount]);
  const max = Math.max(1, ...wid);
  const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
  const sorted = useMemo(() => [...scores].sort((a, b) => a - b), [scores]);
  const mid = sorted.length ? (sorted.length % 2
    ? sorted[(sorted.length - 1) / 2]
    : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2) : 0;
  // gridline values for the y axis
  const grid = [0.25, 0.5, 0.75, 1];

  return (
    <div>
      <div className="mb-3 grid grid-cols-3 gap-3">
        {[
          [avg.toFixed(1), "Average"],
          [mid.toFixed(1), "Median"],
          [scores.length, "Graded"],
        ].map(([v, l]) => (
          <div key={l}>
            <b className="tnum text-[20px] font-extrabold leading-none text-ink">{v}</b>
            <span className="block pt-0.5 text-[11px] font-bold text-ink3">{l}</span>
          </div>
        ))}
      </div>
      <div className="relative">
        {/* horizontal gridlines */}
        {grid.map((g) => (
          <div key={g} className="pointer-events-none absolute inset-x-0 border-t
            border-dashed border-hair" style={{ bottom: `${g * 100}%` }} />
        ))}
        <div className="flex h-[180px] items-end gap-[5px]">
          {wid.map((c, i) => (
            <div key={i} className="group relative flex h-full flex-1 items-end">
              <motion.div
                className="w-full rounded-t-[5px] bg-branddim transition-colors
                  group-hover:bg-brand"
                style={{ boxShadow: c === max && scores.length ? "0 0 0 1px var(--bg0)" : undefined }}
                initial={reduced ? false : { height: 0 }}
                animate={{ height: `${Math.round((c / max) * 100)}%` }}
                transition={softSpring}
                aria-label={`${i * 10}–${i * 10 + 9}%: ${c} student(s)`} />
              {c > 0 && (
                <span className="pointer-events-none absolute -top-6 left-1/2
                  -translate-x-1/2 rounded bg-[var(--bg3)] px-1.5 py-0.5 text-[10px]
                  font-bold text-ink opacity-0 transition-opacity group-hover:opacity-100">
                  {c}</span>)}
            </div>
          ))}
        </div>
        {/* mean line */}
        {scores.length > 0 && (
          <div className="pointer-events-none absolute inset-y-0 w-px bg-brand/70"
            style={{ left: `${(avg / 100) * 100}%` }}
            title={`mean ${avg.toFixed(1)}%`} />
        )}
        <div className="mt-2 flex justify-between text-[10px] font-semibold text-ink3">
          <span>0%</span><span>50%</span><span>100%</span>
        </div>
      </div>
    </div>
  );
});

/* ------------------------------------------------- question difficulty bars */
export const DiffBars = memo(function DiffBars({ questions = [], max = 8 }) {
  const reduced = useReducedMotion();
  const rows = useMemo(() => [...questions]
    .sort((a, b) => b.error_rate - a.error_rate).slice(0, max), [questions, max]);
  return (
    <ul className="space-y-2.5">
      {rows.map((q) => {
        const pct = Math.round(q.error_rate * 100);
        const dTone = q.discrimination < 0 ? "var(--err)"
          : q.discrimination < 0.15 ? "var(--warn)" : "var(--ok)";
        return (
          <li key={q.q} className="group" title={`Q${q.q}: ${pct}% wrong · discrimination ${q.discrimination.toFixed(2)}`}>
            <div className="mb-1 flex items-baseline justify-between text-[11.5px]">
              <b className="tnum font-mono text-ink2">Q{q.q}</b>
              <span className="tnum font-bold" style={{ color: "var(--tx3)" }}>
                {pct}% wrong</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-[13px] flex-1 overflow-hidden rounded-full bg-[var(--bg3)]">
                <motion.div className="h-full rounded-full"
                  style={{ background: "linear-gradient(90deg, var(--brand), var(--brand))" }}
                  initial={reduced ? { width: `${pct}%` } : { width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={softSpring} />
              </div>
              {/* discrimination dot */}
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: dTone }}
                title={`discrimination ${q.discrimination.toFixed(2)}`} />
            </div>
          </li>
        );
      })}
    </ul>
  );
});

/* ------------------------------------------------------- delta / trend chip */
export const Delta = memo(function Delta({ children, dir = "up", tone = "ok" }) {
  const color = { ok: "var(--ok)", warn: "var(--warn)", err: "var(--err)",
    brand: "var(--brand)" }[tone] || "var(--ok)";
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5
      text-[10.5px] font-extrabold" style={{ color, background: `color-mix(in srgb, ${color} 12%, transparent)` }}>
      <svg width="9" height="9" viewBox="0 0 10 10" className={dir === "down" ? "rotate-180" : ""}>
        <path d="M5 8 L1 3 H9 Z" fill={color} />
      </svg>
      {children}
    </span>
  );
});
