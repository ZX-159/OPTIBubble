import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArchiveRestore, FileText, Pencil, Plus, Trash2, Upload } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../App";
import { useFetch } from "../lib/hooks";
import { Badge, Button, Card, EmptyState, ErrorState, Field, IconButton,
         Input, Modal, Skeleton, useToast, spring } from "../components/ui";

export default function TestList() {
  const { state, goto, refresh } = useApp();
  const { data: tests, error, loading, reload } = useFetch("/api/tests");
  const results = useFetch("/api/results");
  const toast = useToast();
  const [busyId, setBusyId] = useState(null);
  const [del, setDel] = useState(null);
  const [arch, setArch] = useState(null);
  const [archPw, setArchPw] = useState("");
  const [archBusy, setArchBusy] = useState(false);
  const [archErr, setArchErr] = useState(null);
  const [edit, setEdit] = useState(null);
  const [edTitle, setEdTitle] = useState("");
  const [edKey, setEdKey] = useState("");
  const [edBusy, setEdBusy] = useState(false);
  const [edErr, setEdErr] = useState(null);
  const [impBusy, setImpBusy] = useState(false);
  const doImport = async (file, pw) => {
    setImpBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    if (pw) fd.append("password", pw);
    try {
      const r = await api("/api/archive/restore", { method: "POST", body: fd });
      toast(`Restored ${r.test_id} (${r.files} files)`, "ok");
      await refresh(true); await reload(true);
    } catch (e) { toast(e.message, "err"); }
    setImpBusy(false);
  };
  const pickImport = () => {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.accept = ".optibubble,.zip";
    inp.onchange = () => {
      const f = inp.files?.[0];
      if (!f) return;
      const pw = prompt("Archive password (leave empty if none):");
      if (pw === null) return;
      doImport(f, pw);
    };
    inp.click();
  };
  useEffect(() => {
    const openArch = (e) => { setArch(e.detail); setArchPw(""); setArchErr(null); };
    const openEdit = (e) => {
      const t = e.detail;
      api(`/api/tests/${t.test_id}`).then((d) => {
        setEdit(d.test || t);
        setEdTitle(d.test?.title || t.title || "");
        setEdKey(Object.entries(d.test?.answer_key || {})
          .sort((a, b) => a[0] - b[0]).map(([q, a]) => `${q}:${a}`).join(" "));
        setEdErr(null);
      }).catch(() => setEdit(t));
    };
    window.addEventListener("ob-archive", openArch);
    window.addEventListener("ob-edit", openEdit);
    return () => { window.removeEventListener("ob-archive", openArch);
                   window.removeEventListener("ob-edit", openEdit); };
  }, []);

  const open = async (id) => {
    setBusyId(id);
    try {
      await api(`/api/tests/${id}/open`, { method: "POST" });
      toast("Test opened — session, review and results now show it", "ok");
      await refresh(true); await reload(true); goto("session");
    } catch (e) { toast(e.message, "err"); }
    setBusyId(null);
  };
  const doDelete = async () => {
    try {
      await api(`/api/tests/${del.test_id}/delete`, { method: "POST" });
      toast("Test deleted", "ok");
      setDel(null); await refresh(true); await reload(true);
    } catch (e) { toast(e.message, "err"); setDel(null); }
  };

  const letters = edit ? "ABCDEFGHIJ".slice(0, edit.options_per_question || 4) : "ABCDE";
  const editRe = new RegExp(`(\\d{1,3})\\s*[:.\\-]\\s*([${letters}])`, "g");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0">
          <h1 className="text-[20px] font-bold tracking-[-0.015em] text-ink">Tests</h1>
          <p className="text-[13px] text-ink3">Every test keeps its own sheets, review queue and CSV.</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" icon={Upload} loading={impBusy} onClick={pickImport}>Import</Button>
          <Button icon={Plus} onClick={() => goto("setup")}>New test</Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          [results.data?.length || 0, "Graded sheets", "text-ok"],
          [state?.stats?.pending_review || 0, "Awaiting review", "text-warn"],
          [tests?.length || 0, "Saved tests", "text-brand"],
          [state?.stats?.rejected || 0, "Rejected", "text-ink"],
        ].map(([n, label, tone]) => (
          <div key={label} className="panel glass px-5 py-4">
            <b className={`block text-[26px] font-extrabold leading-none ${tone}`}>{n}</b>
            <span className="block pt-1.5 text-[11.5px] font-bold text-ink3">{label}</span>
          </div>
        ))}
      </div>

      <Card>
        {loading && !tests ? (
          <div className="space-y-2">{[0, 1, 2].map((i) =>
            <Skeleton key={i} className="h-12 w-full"/>)}</div>
        ) : error ? <ErrorState error={error} onRetry={() => reload()}/>
        : !tests?.length ? (
          <EmptyState icon={FileText} title="No tests yet">
            Create your first answer sheet — it takes under a minute.
          </EmptyState>
        ) : (
          <ul className="space-y-1.5">
            <AnimatePresence initial={false}>
              {tests.map((t) => (
                <motion.li key={t.test_id} layout transition={spring}
                  initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  className="flex min-w-0 items-center gap-3 rounded-xl border border-hair
                    bg-[var(--bg2)] px-3.5 py-2.5">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center
                    rounded-lg bg-branddim text-brand"><FileText size={16}/></span>
                  <div className="min-w-0 flex-1">
                    <b className="block truncate text-[13.5px] text-ink">{t.title}</b>
                    <span className="tnum block font-mono text-[11px] text-ink3">
                      {t.test_id} · {t.num_questions}×{t.options_per_question} ·
                      graded {t.graded || 0}</span>
                  </div>
                  {state?.test?.test_id === t.test_id && <Badge tone="info">active</Badge>}
                  <Button variant="ghost" loading={busyId === t.test_id}
                    onClick={() => open(t.test_id)}>Open</Button>
                  <IconButton icon={ArchiveRestore} label="Archive (encrypted)"
                    onClick={() => window.dispatchEvent(
                      new CustomEvent("ob-archive", { detail: t }))}/>
                  <IconButton icon={Pencil} label="Edit"
                    onClick={() => window.dispatchEvent(
                      new CustomEvent("ob-edit", { detail: t }))}/>
                  <IconButton icon={Trash2} label="Delete" tone="danger"
                    onClick={() => setDel(t)}/>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </Card>

      <AnimatePresence>
        {del && (
          <Modal title={`Delete “${del.title}”?`} onClose={() => setDel(null)}>
            <p className="text-[13px] leading-relaxed text-ink2">
              This permanently removes its answer sheet, every received photo,
              the review queue and <b>all graded results</b>. It cannot be undone.</p>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDel(null)}>Keep it</Button>
              <Button variant="danger" icon={Trash2} onClick={doDelete}>
                Delete everything</Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {arch && (
          <Modal title={`Archive “${arch.title}”`} onClose={() => setArch(null)}>
            <p className="mb-3 text-[13px] leading-relaxed text-ink2">
              Packages the whole test — sheet, key, photos, crops and results —
              into one <code>.optibubble</code> file — optionally encrypted (AES-256).</p>
            <Field label="Password (optional)"
              hint="Leave empty for a plain, unencrypted archive."
              error={archErr}>
              <Input value={archPw} type="password" placeholder="archive password"
                onChange={(e) => setArchPw(e.target.value)}/>
            </Field>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setArch(null)}>Cancel</Button>
              <Button icon={ArchiveRestore} loading={archBusy}
                onClick={async () => {
                  if (archPw && archPw.length < 4) {
                    setArchErr("Password needs 4+ characters (or leave it empty)."); return; }
                  setArchBusy(true); setArchErr(null);
                  try {
                    const r = await fetch(`/api/tests/${arch.test_id}/archive`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ password: archPw }) });
                    if (!r.ok) throw await r.json();
                    const blob = await r.blob();
                    const a = document.createElement("a");
                    a.href = URL.createObjectURL(blob);
                    a.download = arch.test_id + ".optibubble";
                    a.click(); URL.revokeObjectURL(a.href);
                    setArch(null);
                    toast(archPw ? "Encrypted archive downloaded"
                                 : "Archive downloaded (no password)", "ok");
                  } catch (e) { setArchErr((e && e.error) || "failed"); }
                  finally { setArchBusy(false); }
                }}>Download archive</Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {edit && (
          <Modal title="Edit test" onClose={() => setEdit(null)}>
            <p className="mb-3 text-[12.5px] leading-relaxed text-ink3">
              Structure (questions, options, paper) is fixed once printed —
              everything else can change.</p>
            <Field label="Title">
              <Input value={edTitle} maxLength={80}
                onChange={(e) => setEdTitle(e.target.value)}/></Field>
            <Field label="Answer key"
              hint="Replace the whole key · leave empty to keep the current one.">
              <Input value={edKey} className="font-mono text-[12px]"
                placeholder="1:A 2:C … or ABCD…" onChange={(e) => setEdKey(e.target.value)}/></Field>
            {edErr && <p className="mb-2 text-[12px] font-semibold text-err">• {edErr}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setEdit(null)}>Cancel</Button>
              <Button icon={Pencil} loading={edBusy}
                onClick={async () => {
                  setEdBusy(true); setEdErr(null);
                  try {
                    const body = { title: edTitle };
                    const kt = edKey.trim();
                    if (kt) {
                      const entries = {};
                      (kt.toUpperCase().match(editRe) || [])
                        .forEach((m) => { const g = m.match(editRe);
                                           entries[+g[1]] = g[2]; });
                      if (!Object.keys(entries).length) {
                        const compactRe = new RegExp(`[^${letters}]`, "g");
                        [...kt.toUpperCase().replace(compactRe, "")].forEach(
                          (a, i) => { entries[i + 1] = a; });
                      }
                      body.answer_key = entries;
                    }
                    const r = await api(`/api/tests/${edit.test_id}/edit`, {
                      method: "POST", body: JSON.stringify(body) });
                    if (r.ok) {
                      setEdit(null); toast("Test updated — sheet PDF refreshed", "ok");
                      await refresh(true); await reload(true);
                    }
                  } catch (e) { setEdErr(e.message); }
                  setEdBusy(false);
                }}>Save changes</Button>
            </div>
          </Modal>
        )}
      </AnimatePresence>
    </div>
  );
}
