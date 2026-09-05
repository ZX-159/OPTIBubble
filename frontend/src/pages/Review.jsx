import React, { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Check, Eye, ListChecks, Trash2, X } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../App";
import { usePoll } from "../lib/hooks";
import { Badge, Button, Card, EmptyState, ErrorState, Input, Modal,
         Skeleton, spring, useToast } from "../components/ui";

const isID = (f) => f.q == null && f.digit != null;
const kindLabel = { BLANK: "Unanswered", MULTI: "Double mark",
                    FAINT: "Faint mark", ID: "Student ID" };

export default function Review() {
  const { state, refresh } = useApp();
  const { data: items, error, loading, refresh: reload } = usePoll("/api/review", { ms: 3000 });
  const toast = useToast();
  const [sel, setSel] = useState(null);
  const [overrides, setOverrides] = useState({});
  const [revId, setRevId] = useState("");
  const [busy, setBusy] = useState(false);
  const [zoom, setZoom] = useState(null);
  const [focusIdx, setFocusIdx] = useState(0);
  const item = items?.find((x) => x.sheet_id === sel) || items?.[0];

  useEffect(() => { setSel(item?.sheet_id ?? null); setOverrides({});
    setRevId(item?.student_id || ""); setFocusIdx(0); }, [item?.sheet_id]);

  const letters = useMemo(() => "ABCDE".slice(
    0, state?.test?.options_per_question || 4), [state?.test]);

  const confirm = async () => {
    setBusy(true);
    try {
      const answers = {};
      (item?.flags || []).forEach((f, i) => {
        if (f.q != null) answers[f.q] = overrides[i] ?? f.guess ?? null;
      });
      await api("/api/review/resolve", { method: "POST",
        body: JSON.stringify({ sheet_id: item.sheet_id, answers, student_id: revId })});
      toast("Resolved & exported to CSV", "ok");
      await refresh(true); await reload(true);
    } catch (e) { toast(e.message, "err"); }
    setBusy(false);
  };

  const pick = (i, c) => {
    setOverrides((o) => {
      const n = { ...o, [i]: c };
      if (isID(item.flags[i])) {
        const chars = (revId || "").split("");
        while (chars.length <= item.flags[i].digit) chars.push("0");
        chars[item.flags[i].digit] = c;
        setRevId(chars.join(""));
      }
      return n;
    });
  };

  /* Working keyboard shortcuts: ←/→ move between the disputed items on the
     current sheet, 1–5 (or 0–9 for a digit) pick the answer, B = blank,
     Enter = confirm & export, Esc = close the zoom / leave the sheet. */
  useEffect(() => {
    if (!item || busy) return;
    const n = item.flags.length;
    const picksFor = (f) => isID(f) ? [..."0123456789"] : letters.split("");
    let focused = Math.max(0, Math.min(focusIdx, n - 1));
    const h = (e) => {
      if (e.key === "Escape") { setZoom(null); return; }
      if (e.key === "ArrowRight") { e.preventDefault();
        setFocusIdx((x) => (x + 1) % n); return; }
      if (e.key === "ArrowLeft") { e.preventDefault();
        setFocusIdx((x) => (x - 1 + n) % n); return; }
      if (e.key === "Enter") { e.preventDefault(); confirm(); return; }
      const ch = e.key.toUpperCase();
      const f = item.flags[focused];
      if (ch === "B") { e.preventDefault(); pick(focused, null); return; }
      const opts = picksFor(f);
      if (isID(f)) {
        if ("0123456789".includes(ch)) { e.preventDefault(); pick(focused, ch); }
      } else if (opts.includes(ch)) { e.preventDefault(); pick(focused, ch); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [item, busy, focusIdx, overrides, revId, letters]);

  if (!state?.test) return (
    <Card><EmptyState icon={ListChecks} title="No active test">
      Open or create a test to see its review queue.</EmptyState></Card>);
  if (error) return <Card><ErrorState error={error} onRetry={reload}/></Card>;
  if (loading && !items) return <Card><div className="space-y-2">
    <Skeleton className="h-11 w-full"/><Skeleton className="h-11 w-full"/></div></Card>;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-[20px] font-bold tracking-[-0.015em] text-ink">Review</h1>
        <Badge tone={items?.length ? "warn" : "mute"}>{items?.length || 0} flagged</Badge>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
        <Card title="Flagged sheets"
          sub="Blank · double-marked · faint — one human look, then export.">
          {!items?.length ? (
            <EmptyState icon={ListChecks} title="Nothing flagged">
              Clean sailing — ambiguous sheets appear here automatically.
            </EmptyState>
          ) : (
            <ul className="space-y-1.5">
              {items.map((it) => (
                <li key={it.sheet_id}>
                  <button onClick={() => setSel(it.sheet_id)}
                    className={`focusable flex w-full flex-col items-start gap-0.5 rounded-xl
                      border px-3 py-2.5 text-left ${it.sheet_id === item?.sheet_id
                        ? "border-brand/60 bg-branddim" : "border-hair bg-[var(--bg2)] hov"}`}>
                    <b className="tnum text-[13px] text-ink">{it.student_id || "no ID"}</b>
                    <span className="tnum text-[11px] text-ink3">
                      {it.flags.length} flag{it.flags.length > 1 ? "s" : ""} ·
                      {it.score}/{it.max_score} · {(it.ts || "").slice(11, 16)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {item ? (
          <Card title={`Sheet ${item.student_id || "(no ID)"}`} right={
            <Badge tone="warn">{item.flags.length} to verify</Badge>}>
            <p className="-mt-2 mb-3 text-[12px] text-ink3">
              Pick the intended answer for each disputed item, then export.
              Keyboard: <span className="kbd">←</span><span className="kbd">→</span> move ·
              <span className="kbd">1</span>–<span className="kbd">{letters[letters.length-1]}</span>/<span className="kbd">0</span>–<span className="kbd">9</span> pick ·
              <span className="kbd">B</span> blank · <span className="kbd">Enter</span> confirm.</p>
            <div className="mb-3 flex items-center gap-2.5">
              <span className="text-[11px] font-extrabold uppercase tracking-[.1em] text-ink2">
                Student ID</span>
              <Input value={revId} maxLength={10} onChange={(e) => setRevId(e.target.value)}
                className="max-w-[190px] text-center text-[15px] font-extrabold
                  tracking-widest"/>
            </div>
            <ul className="space-y-2">
              {item.flags.map((f, i) => {
                const choices = isID(f) ? [..."0123456789"] : letters.split("");
                const isFocus = i === Math.min(focusIdx, item.flags.length - 1);
                return (
                  <motion.li key={i} layout transition={spring}
                    className={`grid gap-3 rounded-xl border p-3
                      sm:grid-cols-[minmax(0,260px)_minmax(0,1fr)]
                      ${isFocus ? "border-brand bg-branddim/50" : "border-hair bg-[var(--bg2)]"}`}>
                    {f.crop ? (
                      <button className="penring focusable group sheet overflow-hidden
                        rounded-lg" onClick={() => setZoom({ src: f.crop, cap: f.message })}>
                        <img src={f.crop} alt="evidence" className="h-[132px] w-full
                          object-contain"/>
                        <span className="flex items-center justify-center gap-1.5 bg-white
                          py-1.5 text-[10px] font-extrabold uppercase tracking-[.1em]
                          text-[#5B6779] group-hover:text-[var(--vermilion)]">
                          <Eye size={11}/> evidence · click to enlarge</span>
                      </button>
                    ) : (
                      <div className="flex h-full min-h-[80px] items-center justify-center
                        rounded border border-hair2 bg-white/5 text-[12px] text-ink3">
                        no preview</div>
                    )}
                    <div className="min-w-0">
                      <b className={`font-mono text-[11px] uppercase tracking-[.12em]
                        ${isID(f) ? "text-brand" : "penline"}`}>
                        {kindLabel[f.kind] || f.kind}</b>
                      <p className="mb-2 text-[12.5px] text-ink3">{f.message}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {choices.map((c) => {
                          const active = (overrides[i] ?? f.guess ?? null) === c;
                          return (
                            <button key={c} onClick={() => pick(i, c)}
                              className={`focusable hov min-w-[32px] rounded-lg px-2.5
                                py-2 text-[13px] font-extrabold
                                ${active ? "bg-brand text-brandink" : "bg-[var(--bg3)] text-ink"}`}>
                              {c}</button>
                          );
                        })}
                        <button onClick={() => pick(i, null)}
                          className={`focusable hov rounded-lg px-3 py-2 text-[12px]
                            font-extrabold ${(overrides[i] ?? f.guess ?? null) === null
                              ? "bg-brand text-brandink" : "bg-[var(--bg3)] text-ink"}`}>
                          Blank</button>
                      </div>
                    </div>
                  </motion.li>
                );
              })}
            </ul>
            <div className="mt-4 flex gap-2">
              <Button variant="ok" icon={Check} className="flex-1" loading={busy}
                onClick={confirm}>Confirm & export</Button>
              <Button variant="ghost" icon={Trash2}
                onClick={async () => {
                  await api("/api/review/discard", { method: "POST",
                    body: JSON.stringify({ sheet_id: item.sheet_id })});
                  toast("Sheet discarded");
                  await refresh(true); await reload(true);
                }}>Discard</Button>
            </div>
          </Card>
        ) : (
          <Card><EmptyState icon={ListChecks} title="Nothing flagged">
            Ambiguous sheets appear here automatically.</EmptyState></Card>
        )}
      </div>

      <AnimatePresence>
        {zoom && (
          <motion.div className="fixed inset-0 z-[300] flex cursor-zoom-out flex-col
            items-center justify-center gap-3 p-6"
            style={{ background: "rgba(20,25,33,.9)", backdropFilter: "blur(4px)" }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setZoom(null)}>
            <motion.img src={zoom.src} alt="evidence"
              initial={{ scale: 0.94 }} animate={{ scale: 1 }} transition={spring}
              className="max-w-[min(92vw,900px)] max-h-[74vh] rounded bg-white p-2"/>
            <p className="flex items-center gap-2 text-[12.5px] text-ink2">
              <Eye size={13}/>{zoom.cap} · click anywhere to close</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
