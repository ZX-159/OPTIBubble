import React, { memo, useMemo } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  AlertTriangle, ArrowRight, Check, CircleCheck, FileCheck2, Gauge, History,
  Inbox, Layers, ListChecks, Plus, QrCode, Send, ShieldAlert, Sparkles,
  Target, TrendingUp, XCircle, Zap,
} from "lucide-react";
import { useApp } from "../App";
import { useFetch } from "../lib/hooks";
import { AnimatedNum, Button, Card, EmptyState, ErrorState,
         Skeleton, spring, softSpring } from "../components/ui";
import { Spark, RadialGauge, ScoreHistogram, DiffBars } from "../components/charts";

/* ------------------------------------------------------------------ helpers */
const fmtTime = (ts) => {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  const s = (new Date() - d) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

/* ------------------------------------------------------------------ KPI card
   Premium dashboard tile: icon chip + context caption, big animated numeral,
   label, then a real sparkline that reflects the actual data shape. */
const Kpi = memo(function Kpi({ label, value, suffix, sub, icon: Icon, tone,
  accent, spark, sparkColor, onTap }) {
  return (
    <motion.button onClick={onTap}
      variants={{ show: { opacity: 1, y: 0, transition: softSpring } }}
      className="group flex h-full w-full flex-col overflow-hidden rounded-card
        border border-hair bg-[var(--bg1)] p-5 text-left transition-[box-shadow,transform]
        duration-200 focusable hov"
      style={{ boxShadow: "var(--shadow-card)" }}>
      <span className="flex w-full items-start justify-between gap-3">
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${accent}`}>
          <Icon size={19} />
        </span>
        {sub && <span className="pointer-events-none mt-0.5 max-w-[58%] truncate
          text-right text-[11px] font-bold text-ink3">{sub}</span>}
      </span>
      <span className={`mt-4 block text-[38px] font-extrabold leading-none
        tracking-[-0.02em] ${tone}`}><AnimatedNum value={value} />{suffix}</span>
      <span className="mt-1.5 block text-[12.5px] font-extrabold text-ink2">{label}</span>
      {spark?.length > 1 && (
        <span className="mt-auto block w-full pl-1 pt-3">
          <Spark data={spark} color={sparkColor} height={34} />
        </span>
      )}
    </motion.button>
  );
});

/* ------------------------------------------------------------------ analytics */
function AnalyticsCard({ data, loading, error, reload }) {
  if (loading && !data) return <div className="space-y-2">{[
    0, 1, 2].map((i) => <Skeleton key={i} className="h-4 w-full" /> )}</div>;
  if (error) return <ErrorState error={error} onRetry={() => reload()} />;
  if (!data || data.n < 2 || !data.questions?.length) {
    return <div className="flex h-full min-h-[200px] items-center justify-center">
      <EmptyState icon={Gauge} title="At least 2 graded sheets">
        KR-20 reliability and question analytics unlock once 2+ sheets are graded.</EmptyState>
    </div>;
  }
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-4">
        <RadialGauge value={data.kr20} tone={
          data.kr20 >= 0.8 ? "var(--ok)" : data.kr20 >= 0.6 ? "var(--warn)" : "var(--err)"}
          size={116} />
        <div className="min-w-0 flex-1">
          <b className="block text-[14px] leading-tight text-ink">KR-20 reliability</b>
          <span className="text-[11.5px] text-ink3">{data.n} graded · {
            data.kr20 >= 0.8 ? "strong" : data.kr20 >= 0.6 ? "moderate" : "low"} consistency</span>
          <div className="mt-2 space-y-1 text-[11px] text-ink3">
            <div className="flex justify-between"><span>Mean</span>
              <b className="tnum text-ink2">{data.mean}</b></div>
            <div className="flex justify-between"><span>Median</span>
              <b className="tnum text-ink2">{data.median}</b></div>
            <div className="flex justify-between"><span>σ Dev</span>
              <b className="tnum text-ink2">{data.stdev}</b></div>
          </div>
        </div>
      </div>
      <div className="mt-4 border-t border-hair pt-3">
        <p className="mb-2.5 text-[11px] font-extrabold uppercase tracking-[.12em]
          text-ink3">Hardest questions <span className="font-mono normal-case tracking-normal">
            · D = discrimination</span></p>
        <DiffBars questions={data.questions} max={4} />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ recent activity */
const EV = {
  server_started: { icon: Zap, tone: "bg-okdim text-ok", label: "Session live",
    text: (e) => "Submission server is running" },
  sheet_graded: { icon: CircleCheck, tone: "bg-okdim text-ok", label: "Auto-graded",
    text: (e) => `${e.result?.student_id || "sheet"} got ${e.result?.score}/${e.result?.max}` },
  sheet_flagged: { icon: ShieldAlert, tone: "bg-warndim text-warn", label: "Needs review",
    text: (e) => `${e.result?.student_id || "sheet"} flagged (${e.result?.flags?.length || 0} issue${(e.result?.flags?.length || 0) === 1 ? "" : "s"})` },
  review_resolved: { icon: Check, tone: "bg-branddim text-brand", label: "Review resolved",
    text: (e) => `${e.student_id || e.sheet_id} confirmed at ${e.score}` },
  review_discarded: { icon: XCircle, tone: "bg-[var(--bg3)] text-ink3", label: "Discarded",
    text: (e) => `review ${e.sheet_id}` },
  sheet_rejected: { icon: AlertTriangle, tone: "bg-errdim text-err", label: "Rejected",
    text: (e) => e.message || "sheet could not be graded" },
  test_created: { icon: Plus, tone: "bg-branddim text-brand", label: "Test created",
    text: (e) => e.title },
  test_opened: { icon: Layers, tone: "bg-branddim text-brand", label: "Test opened",
    text: (e) => e.title },
  server_stopped: { icon: XCircle, tone: "bg-[var(--bg3)] text-ink3", label: "Stopped",
    text: () => "Submission server stopped" },
  settings_saved: { icon: Target, tone: "bg-[var(--bg3)] text-ink3", label: "Settings",
    text: () => "Settings saved" },
};
function RecentActivity({ log }) {
  const reduced = useReducedMotion();
  const items = useMemo(() => (log || [])
    .filter((e) => EV[e.type] && e.type !== "settings_saved")
    .sort((a, b) => b.ts - a.ts)
    .slice(0, 8), [log]);
  if (!items.length) {
    return <EmptyState icon={History} title="Nothing here yet">
      Activity appears as sheets arrive and reviews are resolved.</EmptyState>;
  }
  return (
    <ul className="space-y-1">
      <AnimatePresence initial={false}>
        {items.map((e) => {
          const ev = EV[e.type];
          const Icon = ev.icon;
          return (
            <motion.li key={e.ts + e.type} layout transition={spring}
              initial={reduced ? false : { opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-3 rounded-lg px-2 py-2">
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center
                rounded-lg ${ev.tone}`}><Icon size={15} /></span>
              <div className="min-w-0 flex-1">
                <b className="block truncate text-[12.5px] text-ink">{ev.label}</b>
                <span className="block truncate text-[11.5px] text-ink3">{ev.text(e)}</span>
              </div>
              <span className="shrink-0 text-[10.5px] font-semibold text-ink3">
                {fmtTime(e.ts)}</span>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ul>
  );
}

/* ------------------------------------------------------------------ next step */
function NextStep({ state, goto }) {
  const t = state?.test;
  if (!t) {
    return (
      <div className="relative flex h-full flex-col overflow-hidden rounded-card
        border border-hair bg-[var(--bg1)] p-5" style={{ boxShadow: "var(--shadow-card)" }}>
        <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32
          rounded-full bg-branddim blur-2xl" />
        <span className="flex h-11 w-11 items-center justify-center rounded-xl
          bg-branddim text-brand"><ListChecks size={20} /></span>
        <h3 className="mt-3 text-[16px] font-bold text-ink">Start a test</h3>
        <p className="mt-1 text-[13px] leading-relaxed text-ink3">
          Create an answer sheet, share its link or QR code, then let the app
          grade the returned photos.</p>
        <div className="mt-auto flex flex-wrap gap-2 pt-4">
          <Button icon={Plus} onClick={() => goto("setup")}>Create a test</Button>
          <Button variant="ghost" onClick={() => goto("help")}>How it works</Button>
        </div>
      </div>
    );
  }
  const pending = state?.stats?.pending_review || 0;
  if (pending > 0) {
    return <StepCard tone="warn" icon={Inbox} title={`${pending} sheet${pending === 1 ? "" : "s"} await review`}
      copy="A human decision resolves a flagged sheet — confirm, correct the marks, then export."
      cta="Open review queue" onCta={() => goto("review")} />;
  }
  const results = state?.stats?.exported || 0;
  if (results === 0) {
    const ready = state?.server?.running;
    return <StepCard tone={ready ? "ok" : "brand"} icon={ready ? Send : QrCode}
      title={ready ? "Share the link & scan" : "Start the submission server"}
      copy={ready ? `Session live — scan the QR or share ${state.server?.url || "the link"} to collect sheets.`
        : "Start the local server to hand out the QR code to students."}
      cta={ready ? "View session" : "Start session"} onCta={() => goto("session")} />;
  }
  return <StepCard tone="brand" icon={Sparkles} title="All graded — review the results"
    copy={`${results} sheet${results === 1 ? "" : "s"} exported. Analyse scores, questions and KR-20.`}
    cta="Open results" onCta={() => goto("results")} />;
}

function StepCard({ tone, icon: Icon, title, copy, cta, onCta }) {
  const meta = {
    brand: "bg-branddim text-brand", ok: "bg-okdim text-ok",
    warn: "bg-warndim text-warn", err: "bg-errdim text-err",
  }[tone];
  return (
    <div className="relative flex h-full flex-col overflow-hidden rounded-card
      border border-hair bg-[var(--bg1)] p-5" style={{ boxShadow: "var(--shadow-card)" }}>
      <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32
        rounded-full bg-branddim blur-2xl" />
      <div className="flex items-start gap-3">
        <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${meta}`}>
          <Icon size={20} /></span>
        <div className="min-w-0 flex-1">
          <h3 className="text-[16px] font-bold text-ink">{title}</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-ink3">{copy}</p>
        </div>
      </div>
      <div className="mt-auto flex justify-end pt-4">
        <Button icon={ArrowRight} onClick={onCta}>{cta}</Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ the page */
export default function Dashboard() {
  const { state, goto } = useApp();
  const reduced = useReducedMotion();
  const results = useFetch("/api/results");
  const analytics = useFetch("/api/analytics");

  // derive real aggregates once per render
  const { rows, pcts, mean, median, dist, cdf } = useMemo(() => {
    const rows = results.data || [];
    const pcts = rows.map((r) => Number(r?.Percent ?? r?.percent)).filter(Number.isFinite);
    const mean = pcts.length ? pcts.reduce((a, b) => a + b, 0) / pcts.length : 0;
    const sorted = [...pcts].sort((a, b) => a - b);
    const median = sorted.length ? (sorted.length % 2
      ? sorted[(sorted.length - 1) / 2]
      : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2) : 0;
    const dist = Array.from({ length: 9 }, () => 0);
    pcts.forEach((s) => { dist[Math.min(8, Math.floor(s / (100 / 9)))] += 1; });
    // asc CDF (percentile vs score) = real distribution curve
    const cdf = sorted.map((_, i) => (i + 1));
    return { rows, pcts, mean, median, dist, cdf };
  }, [results.data]);

  const s = state?.stats || {};
  const t = state?.test;

  const kpis = [
    { key: "graded", label: "Graded sheets", value: rows.length, suffix: "",
      sub: t ? `${t.num_questions} questions` : "across sessions",
      icon: FileCheck2, tone: "text-ok", accent: "bg-okdim text-ok",
      spark: cdf, sparkColor: "var(--ok)", onTap: () => goto("tests") },
    { key: "mean", label: "Mean score", value: Math.round(mean), suffix: "%",
      sub: `median ${median.toFixed(1)}%`, icon: Gauge, tone: "text-brand",
      accent: "bg-branddim text-brand", spark: cdf, sparkColor: "var(--brand)",
      onTap: () => goto("results") },
    { key: "review", label: "Awaiting review", value: s.pending_review || 0, suffix: "",
      sub: s.pending_review ? "flagged to confirm" : "queue clear",
      icon: ListChecks, tone: "text-warn", accent: "bg-warndim text-warn",
      spark: cdf, sparkColor: "var(--warn)", onTap: () => goto("review") },
    { key: "reject", label: "Rejected", value: s.rejected || 0, suffix: "",
      sub: "auto-rejected", icon: XCircle, tone: "text-ink2",
      accent: "bg-[var(--bg3)] text-ink2", spark: cdf, sparkColor: "var(--tx3)",
      onTap: null },
  ];

  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long", month: "long", day: "numeric" });

  return (
    <div className="space-y-5">
      {/* header */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="text-[13px] font-bold text-ink3">{today}</p>
          <h1 className="text-[26px] font-extrabold tracking-[-0.02em] text-ink">
            {t ? "Welcome back" : "Dashboard"}</h1>
          <p className="mt-0.5 text-[13.5px] text-ink2">
            {t ? <>Active test · <b className="text-ink">{t.title}</b></>
              : "Set up a test to start grading."}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button variant={t ? "ghost" : "primary"} icon={Plus}
            onClick={() => goto("setup")}>New test</Button>
          {t && <Button icon={QrCode} onClick={() => goto("session")}>
            Scan &amp; serve</Button>}
        </div>
      </div>

      {/* motion choreography */}
      <motion.div className="space-y-5" initial={reduced ? false : "hidden"}
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.05 } } }}>

        {/* KPI grid */}
        <motion.div className="grid grid-cols-2 gap-4 lg:grid-cols-4"
          variants={{ hidden: { opacity: 0 }, show: { opacity: 1,
            transition: { staggerChildren: 0.06 } } }}>
          {kpis.map((k) => (
            <motion.div key={k.key} className="h-full"
              variants={{ hidden: { opacity: 0, y: 12 },
                show: { opacity: 1, y: 0, transition: softSpring } }}>
              <Kpi {...k} />
            </motion.div>
          ))}
        </motion.div>

        {/* charts row */}
        <motion.div className="grid grid-cols-1 gap-4 lg:grid-cols-3"
          variants={{ hidden: { opacity: 0 }, show: { opacity: 1,
            transition: { staggerChildren: 0.06 } } }}>
          <motion.div variants={{ hidden: { opacity: 0, y: 14 },
            show: { opacity: 1, y: 0, transition: softSpring } }}
            className="lg:col-span-2">
            <Card title="Score distribution" className="h-full"
              sub={`${rows.length} graded sheet${rows.length === 1 ? "" : "s"}`}>
              {results.loading && !results.data
                ? <div className="space-y-2">{[0, 1, 2].map((i) =>
                    <Skeleton key={i} className="h-5 w-full" /> )}</div>
                : results.error
                  ? <ErrorState error={results.error} onRetry={() => results.reload()} />
                  : rows.length
                    ? <ScoreHistogram scores={pcts} />
                    : <EmptyState icon={TrendingUp} title="No scores yet">
                        Grade a sheet and the score distribution appears here.</EmptyState>}
            </Card>
          </motion.div>

          <motion.div variants={{ hidden: { opacity: 0, y: 14 },
            show: { opacity: 1, y: 0, transition: softSpring } }} className="h-full">
            <Card title="Analytics" className="h-full"
              sub="reliability & question quality">
              <AnalyticsCard data={analytics.data} loading={analytics.loading}
                error={analytics.error} reload={analytics.reload} />
            </Card>
          </motion.div>
        </motion.div>

        {/* lower row */}
        <motion.div className="grid grid-cols-1 gap-4 lg:grid-cols-3"
          variants={{ hidden: { opacity: 0 }, show: { opacity: 1,
            transition: { staggerChildren: 0.06 } } }}>
          <motion.div variants={{ hidden: { opacity: 0, y: 14 },
            show: { opacity: 1, y: 0, transition: softSpring } }}
            className="lg:col-span-2">
            <Card title="Recent activity" className="h-full" sub="the last 8 events">
              <RecentActivity log={state?.log} />
            </Card>
          </motion.div>
          <motion.div variants={{ hidden: { opacity: 0, y: 14 },
            show: { opacity: 1, y: 0, transition: softSpring } }}>
            <NextStep state={state} goto={goto} />
          </motion.div>
        </motion.div>
      </motion.div>

      {/* how it flows */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          ["Create", ListChecks, "Design the answer sheet with an answer key.", "setup"],
          ["Collect", QrCode, "Share the link or QR code to receive photos.", "session"],
          ["Grade", Zap, "Auto-grade the marks; review only what it flags.", "review"],
        ].map(([label, Icon, copy, page], i) => (
          <button key={label} onClick={() => goto(page)}
            className="group flex items-center gap-3 rounded-card border border-hair
              bg-[var(--bg1)] p-4 text-left transition-shadow focusable hov"
            style={{ boxShadow: "var(--shadow-card)" }}>
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg
              bg-branddim text-brand"><Icon size={17} /></span>
            <span className="min-w-0 flex-1">
              <b className="block text-[13.5px] text-ink">{label}</b>
              <span className="block text-[12px] leading-snug text-ink3">{copy}</span>
            </span>
            <ArrowRight size={15} className="shrink-0 text-ink3 transition-transform
              group-hover:translate-x-0.5 group-hover:text-brand" />
          </button>
        ))}
      </div>
    </div>
  );
}
