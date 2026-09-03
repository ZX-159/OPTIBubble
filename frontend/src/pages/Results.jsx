import React, { useState } from "react";
import { motion } from "motion/react";
import { Download, FolderOpen, Table2 } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../App";
import { usePoll } from "../lib/hooks";
import { Badge, Card, ConfBar, EmptyState, ErrorState, Input, Modal,
         Skeleton } from "../components/ui";

function Analytics() {
  const { data: a, error } = usePoll("/api/analytics", { ms: 8000 });
  if (error) return null;
  if (!a) return <Card title="Analytics"><Skeleton className="h-16 w-full"/></Card>;
  if (a.kr20 == null) return (
    <Card title="Analytics"><p className="text-[12px] text-ink3">
      {a.note || "Grade a few sheets to see reliability statistics."}</p></Card>);
  const tone = a.kr20 >= 0.8 ? "ok" : a.kr20 >= 0.6 ? "warn" : "err";
  const worst = (a.questions || []).slice().sort((x, y) => y.error_rate - x.error_rate);
  return (
    <Card title="Analytics" right={
      <><Badge tone={tone}>KR-20 {a.kr20.toFixed(2)}</Badge>
        <span className="tnum hidden text-[11px] text-ink3 sm:block">
          n={a.n} · {a.k} items · mean {a.mean} · σ {a.stdev}</span></>}>
      <div className="space-y-1.5">
        {worst.slice(0, 8).map((q) => {
          const dTone = q.discrimination < 0 ? "err"
            : q.discrimination < 0.15 ? "warn" : "ok";
          return (
            <div key={q.q} className="grid grid-cols-[36px_minmax(0,1fr)_84px_72px]
              items-center gap-2.5 text-[11.5px]">
              <b className="tnum">Q{q.q}</b>
              <div title={`${Math.round(q.error_rate * 100)}% wrong`}>
                <div className="h-[5px] w-full overflow-hidden rounded bg-fill">
                  <motion.div className="h-full bg-brand"
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.round(q.error_rate * 100)}%` }}/>
                </div></div>
              <Badge tone={dTone} className="justify-self-start">
                D {q.discrimination.toFixed(2)}</Badge>
              <span className="tnum text-right text-ink3">
                {Math.round(q.error_rate * 100)}% wrong</span>
            </div>
          );
        })}
      </div>
      <p className="mt-2.5 text-[10.5px] leading-snug text-ink3">
        Top items by error rate · D = discrimination (point-biserial; below 0.15
        = weak item, negative = suspects the key). KR-20 ≥ 0.8 is strong.</p>
    </Card>
  );
}

export default function Results() {
  const { state } = useApp();
  const { data: rows, error, loading, refresh } = usePoll("/api/results", { ms: 5000 });
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState(null);
  if (!state?.test) return (
    <Card><EmptyState icon={Table2} title="No active test">
      Open a test to see its results.</EmptyState></Card>);
  if (error) return <Card><ErrorState error={error} onRetry={refresh}/></Card>;
  const all = rows || [];
  const shown = q ? all.filter((r) => (r.Student_ID || "").includes(q)) : all;
  const scores = shown.map((r) => +r.Total_Score || 0);
  return (
    <div className="space-y-4">
      <Analytics/>
      <Card title="Results" right={
        <>
          {shown.length ? (
            <Badge tone="ok">{shown.length} sheets · avg{" "}
              {(scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1)} ·
              high {Math.max(...scores)} · low {Math.min(...scores)}</Badge>) : null}
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="filter by ID…" className="!w-36"/>
          <a href="/api/results/export.csv"
            className="focusable btn-hov inline-flex items-center gap-1.5 rounded border
              border-hair2 bg-fill px-3 py-2 text-[11.5px] font-extrabold">
            <Download size={13}/> Export CSV</a>
          <button onClick={() => api("/api/reveal", { method: "POST" }).catch(() => {})}
            className="focusable btn-hov inline-flex items-center gap-1.5 rounded border
              border-hair2 bg-fill px-3 py-2 text-[11.5px] font-extrabold">
            <FolderOpen size={13}/> Data folder</button>
        </>}>
        {loading && !rows ? <Skeleton className="h-24 w-full"/> :
        !shown.length ? (
          <EmptyState icon={Table2} title={all.length ? "No match." : "No graded sheets yet"}>
            {all.length ? "Try a different ID." :
              "Graded and verified sheets land here in real time."}</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead><tr className="border-b border-hair2 text-left text-[9.5px]
                uppercase tracking-[.12em] text-ink3">
                {["#", "Time", "Student ID", "Score", "%", "Confidence", "Status"]
                  .map((h) => <th key={h} className="px-2 py-2 font-extrabold">{h}</th>)}
              </tr></thead>
              <tbody>
                {shown.slice().reverse().map((r, i) => {
                  let conf = null;
                  try { conf = JSON.parse(r.Detailed_Answers_JSON || "{}").confidence; } catch {}
                  return (
                    <tr key={r.Timestamp + i} tabIndex={0}
                      onClick={() => setDetail(r)}
                      onKeyDown={(e) => e.key === "Enter" && setDetail(r)}
                      className="cursor-pointer border-b border-hair hover:bg-raised
                        focus-visible:bg-raised">
                      <td className="tnum px-2 py-2 text-ink3">{i + 1}</td>
                      <td className="tnum px-2 py-2 font-mono text-[11px]">
                        {(r.Timestamp || "").slice(11, 19)}</td>
                      <td className="px-2 py-2 font-bold">{r.Student_ID || "—"}</td>
                      <td className="tnum px-2 py-2"><b>{r.Total_Score}</b>
                        <span className="text-ink3">/{r.Max_Score}</span></td>
                      <td className="tnum px-2 py-2">{r.Percent ?? "—"}</td>
                      <td className="px-2 py-2">{conf != null ? <ConfBar v={conf}/> : "—"}</td>
                      <td className="px-2 py-2">
                        {r.Status === "Verified"
                          ? <Badge tone="ok">verified</Badge>
                          : <Badge tone="warn">flagged</Badge>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {detail && (
        <Modal title={detail.Student_ID || "(no ID)"} onClose={() => setDetail(null)}>
          <DetailBody r={detail}/>
        </Modal>
      )}
    </div>
  );
}

function DetailBody({ r }) {
  let d = {};
  try { d = JSON.parse(r.Detailed_Answers_JSON || "{}"); } catch {}
  const answers = d.answers || {}, correct = d.correct || {};
  const qs = Object.keys(answers).map(Number).sort((a, b) => a - b);
  const conf = d.confidence != null ? Math.round(d.confidence * 100) + "%" : "—";
  return (
    <>
      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[["Score", `${r.Total_Score}/${r.Max_Score}`], ["Percent", `${r.Percent ?? "—"}%`],
          ["Confidence", conf], ["Status", r.Status || ""]].map(([k, v]) => (
          <div key={k} className="rounded border border-hair bg-base p-2.5">
            <span className="block text-[9px] font-extrabold uppercase tracking-[.12em]
              text-ink3">{k}</span>
            <b className="tnum text-[13px]">{v}</b>
          </div>
        ))}
      </div>
      <p className="mb-1.5 text-[10px] font-extrabold uppercase tracking-[.14em] text-ink3">
        Per-question answers</p>
      <div className="flex flex-wrap gap-1.5">
        {qs.length ? qs.map((q) => {
          const ok = correct[q];
          return (
            <span key={q} className={`tnum rounded px-1.5 py-1 text-[11px] font-extrabold
              ${ok ? "bg-okdim text-ok" : answers[q] ? "bg-errdim text-err" : "bg-fill text-ink3"}`}>
              {q} | {answers[q] || "—"}</span>
          );
        }) : <span className="text-[12px] text-ink3">no detail stored</span>}
      </div>
    </>
  );
}
