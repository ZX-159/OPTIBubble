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
  const item = items?.find((x) => x.sheet_id === sel) || items?.[0];

  useEffect(() => { setSel(item?.sheet_id ?? null); setOverrides({});
    setRevId(item?.student_id || ""); }, [item?.sheet_id]);
  useEffect(() => {
    const h = (e) => {
      if (!item || busy) return;
      const flags = item.flags; const idx = flags.findIndex(
        (f) => f === flags[Object.keys(overrides).length - 1]); // not used directly
      if (e.key === "Escape") setZoom(null);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [item, busy, overrides]);

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

  if (!state?.test) return (
    <Card><EmptyState icon={ListChecks} title="No active test">
      Open or create a test to see its review queue.</EmptyState></Card>);
  if (error) return <Card><ErrorState error={error} onRetry={reload}/></Card>;
  if (loading && !items) return <Card><div className="space-y-2">
    <Skeleton className="h-10 w-full"/><Skeleton className="h-10 w-full"/></div></Card>;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
      <Card title="Flagged sheets" right={<Badge tone={items?.length ? "warn" : "mute"}>
        {items?.length || 0}</Badge>}
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
                  className={`focusable flex w-full flex-col items-start gap-0.5 rounded
                    border px-3 py-2.5 text-left ${it.sheet_id === item?.sheet_id
                      ? "border-brand/60 bg-raised" : "border-hair bg-base hov"}`}>
                  <b className="tnum text-[12.5px]">{it.student_id || "no ID"}</b>
                  <span className="tnum text-[10.5px] text-ink3">
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
          <p className="-mt-2 mb-3 text-[11.5px] text-ink3">
            Pick the intended answer for each disputed item, then export.
            Keyboard: <kbd>1</kbd>–<kbd>5</kbd>/<kbd>0</kbd>–<kbd>9</kbd> pick ·
            <kbd>B</kbd> blank · <kbd>Enter</kbd> confirm.</p>
          <div className="mb-3 flex items-center gap-2.5">
            <span className="text-[10px] font-extrabold uppercase tracking-[.14em] text-ink2">
              Student ID</span>
            <Input value={revId} maxLength={10} onChange={(e) => setRevId(e.target.value)}
              className="max-w-[180px] text-center text-[14px] font-extrabold
                tracking-[.18px] tracking-widest"/>
          </div>
          <ul className="space-y-2">
            {item.flags.map((f, i) => {
              const choices = isID(f) ? [..."0123456789"] : letters.split("");
              return (
                <motion.li key={i} layout transition={spring}
                  className="grid gap-3 rounded border border-hair bg-base p-3
                    sm:grid-cols-[minmax(0,260px)_minmax(0,1fr)]">
                  {f.crop ? (
                    <button className="penring focusable group sheet overflow-hidden
                      rounded" onClick={() => setZoom({ src: f.crop, cap: f.message })}>
                      <img src={f.crop} alt="evidence" className="h-[132px] w-full
                        object-contain"/>
                      <span className="flex items-center justify-center gap-1.5 bg-white
                        py-1.5 text-[9px] font-extrabold uppercase tracking-[.12em]
                        text-[#5B6779] group-hover:text-[#E23A12]">
                        <Eye size={11}/> evidence · click to enlarge</span>
                    </button>
                  ) : (
                    <div className="flex h-full min-h-[80px] items-center justify-center
                      rounded border border-hair2 bg-white/5 text-[11.5px] text-ink3">
                      no preview</div>
                  )}
                  <div className="min-w-0">
                    <b className={`font-mono text-[11px] uppercase tracking-[.14em]
                      ${isID(f) ? "text-brandhi" : "penline"}`}>
                      {kindLabel[f.kind] || f.kind}</b>
                    <p className="mb-2 text-[12px] text-ink3">{f.message}</p>
                    <div className="flex flex-wrap gap-1">
                      {choices.map((c) => {
                        const active = (overrides[i] ?? f.guess ?? null) === c;
                        return (
                          <button key={c}
                            onClick={() => setOverrides((o) => {
                              const n = { ...o, [i]: c };
                              if (isID(f)) {
                                const chars = (revId || "").split("");
                                while (chars.length <= f.digit) chars.push("0");
                                chars[f.digit] = c;
                                setRevId(chars.join(""));
                              }
                              return n;
                            })}
                            className={`focusable hov min-w-[30px] rounded-[3px] px-2
                              py-1.5 text-[12px] font-extrabold
                              ${active ? "bg-brand text-brandink" : "bg-fill text-ink"}`}>
                            {c}
                          </button>
                        );
                      })}
                      <button
                        onClick={() => setOverrides((o) => ({ ...o, [i]: null }))}
                        className={`focusable hov rounded-[3px] px-2.5 py-1.5 text-[11px]
                          font-extrabold ${(overrides[i] ?? f.guess ?? null) === null
                            ? "bg-brand text-brandink" : "bg-fill text-ink"}`}>
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

      <AnimatePresence>
        {zoom && (
          <motion.div className="fixed inset-0 z-[300] flex cursor-zoom-out flex-col
            items-center justify-center gap-3 p-6"
            style={{ background: "rgba(5,6,9,.9)", backdropFilter: "blur(4px)" }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setZoom(null)}>
            <motion.img src={zoom.src} alt="evidence"
              initial={{ scale: 0.94 }} animate={{ scale: 1 }} transition={spring}
              className="max-w-[min(92vw,900px)] max-h-[74vh] rounded bg-white p-2"/>
            <p className="flex items-center gap-2 text-[12px] text-ink2">
              <Eye size={13}/>{zoom.cap} · click anywhere to close</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
