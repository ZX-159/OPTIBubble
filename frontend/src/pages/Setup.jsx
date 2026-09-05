import React, { useMemo, useState } from "react";
import { Eye, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../App";
import { Badge, Button, Card, Field, Input, Modal, Segmented,
         Textarea, useToast } from "../components/ui";

export default function Setup() {
  const { refresh, goto } = useApp();
  const toast = useToast();
  const [f, setF] = useState({
    title: "", subject: "", num_questions: 20, options_per_question: 4,
    student_id_digits: 7, page_size: "a4", instructions: "",
    header_font_scale: 1, logo_position: "left", write_in: "Name, Class, Date",
    default_points: 1, weights: "", partial: 0,
  });
  const [key, setKey] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [preview, setPreview] = useState(null);
  const set = (k) => (v) => setF((s) => ({ ...s, [k]: v }));
  const letters = "ABCDE".slice(0, f.options_per_question);
  const n = Math.max(2, Math.min(102, +f.num_questions || 20));

  const KeyCell = ({ q }) => {
    const v = key[q];
    return (
      <div className="flex min-w-0 items-center gap-1.5 rounded bg-base px-1.5 py-1">
        <span className="tnum w-7 shrink-0 text-right text-[10px] font-extrabold
          text-ink3">{q}</span>
        <button type="button" onClick={() => setKey((k) => {
          const cur = k[q];
          const next = !cur ? letters[0]
            : cur === letters[letters.length - 1] ? null
            : letters[letters.indexOf(cur) + 1];
          const c = { ...k };
          next ? (c[q] = next) : delete c[q];
          return c;
        })}
          className={`focusable flex-1 rounded-[3px] py-1 text-[11px] font-extrabold
            ${v ? "bg-brand text-brandink" : "bg-fill text-ink3 hov"}`}>
          {v || "–"}
        </button>
      </div>
    );
  };
  const keyCols = useMemo(() => {
    const cols = n > 60 ? 4 : n > 24 ? 3 : n > 8 ? 2 : 1;
    const per = Math.ceil(n / cols);
    return Array.from({ length: cols }, (_, c) =>
      Array.from({ length: per }, (_, r) => c * per + r + 1).filter((q) => q <= n));
  }, [n]);

  const create = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api("/api/tests", {
        method: "POST", body: JSON.stringify({
          title: f.title, subject: f.subject, num_questions: n,
          options_per_question: f.options_per_question,
          student_id_digits: f.student_id_digits, page_size: f.page_size,
          sheet_instructions: f.instructions,
          header_font_scale: +f.header_font_scale, logo_position: f.logo_position,
          write_in_fields: f.write_in, default_points: +f.default_points,
          weights_text: f.weights, partial_multi_credit: +f.partial,
          answer_key: key,
        })});
      if (r.auto_key) toast("Answer key auto-generated — edit it anytime", "ok");
      setPreview(`/api/preview.png?t=${Date.now()}`);
      toast("Test created — sheet ready to print", "ok");
      await refresh(true); goto("serve");
    } catch (e) {
      setErr(e.message);
    } finally { setBusy(false); }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,300px)_minmax(0,1fr)_minmax(0,300px)]">
      <div className="space-y-4">
        <Card title="Test definition">
          <Field label="Test title *">
            <Input value={f.title} maxLength={80}
              placeholder="e.g. Physics Midterm — Form A"
              onChange={(e) => set("title")(e.target.value)}/></Field>
          <Field label="Subject">
            <Input value={f.subject} maxLength={80} placeholder="e.g. Physics"
              onChange={(e) => set("subject")(e.target.value)}/></Field>
          <Field label="Questions (2–102)" hint="1–34 one column · 35–68 two · 69–102 three">
            <Input type="number" min={2} max={102} value={f.num_questions}
              onChange={(e) => set("num_questions")(e.target.value)}/></Field>
          <Field label="Options per question">
            <Segmented value={f.options_per_question} onChange={set("options_per_question")}
              options={[2, 3, 4, 5].map((v) => ({ value: v, label: `${v} · A-${letters[v-1]||"E"}` }))}/></Field>
          <Field label="Student-ID digits">
            <Segmented value={f.student_id_digits} onChange={set("student_id_digits")}
              options={[4, 6, 7, 0].map((v) => ({ value: v, label: v || "none" }))}/></Field>
          <Field label="Paper size">
            <Segmented value={f.page_size} onChange={set("page_size")}
              options={[{ value: "a4", label: "A4" }, { value: "letter", label: "Letter" }]}/></Field>
          {err && <p className="mb-2 text-[11.5px] font-semibold text-err">• {err}</p>}
          <Button variant="ok" className="w-full" loading={busy} onClick={create}>
            Create test & generate sheet</Button>
        </Card>
      </div>

      <Card title="Answer key" right={<Badge tone="info">optional</Badge>}
        sub="Click a cell to cycle options — or leave empty and a balanced key is generated automatically (editable anytime).">
        <div className="mb-3 flex flex-wrap gap-1.5">
          <Button variant="ghost" icon={Sparkles}
            onClick={() => setKey(Object.fromEntries(
              Array.from({ length: n }, (_, i) =>
                [i + 1, letters[Math.floor(Math.random() * letters.length)]])))}>
            Random</Button>
          <Button variant="ghost" onClick={() => setKey({})}>Clear</Button>
        </div>
        <div className="grid gap-1.5"
          style={{ gridTemplateColumns: `repeat(${keyCols.length}, minmax(0,1fr))` }}>
          {keyCols.map((col, i) => (
            <div key={i} className="flex flex-col gap-1.5">
              {col.map((q) => <KeyCell key={q} q={q}/>)}
            </div>
          ))}
        </div>
      </Card>

      <div className="space-y-4">
        <Card title="Sheet design"
          sub="Edits stay inside the header — the answer area is never touched; text auto-shrinks instead of overlapping.">
          <Field label="Sheet instructions">
            <Textarea rows={3} maxLength={240} value={f.instructions}
              placeholder="Leave empty for the default helper text"
              onChange={(e) => set("instructions")(e.target.value)}/></Field>
          <Field label={`Header text size — ${Math.round(f.header_font_scale * 100)}%`}>
            <input type="range" min="0.8" max="1.4" step="0.05"
              value={f.header_font_scale} className="w-full accent-[var(--brand)]"
              onChange={(e) => set("header_font_scale")(+e.target.value)}/></Field>
          <Field label="Wordmark side" hint="Logo prints in brand blue #2e5a99.">
            <Segmented value={f.logo_position} onChange={set("logo_position")}
              options={[{ value: "left", label: "Left" }, { value: "right", label: "Right" }]}/></Field>
          <Field label="Handwritten write-in fields"
            hint="Users fill by hand; the scanner ignores them. Max 6.">
            <Input value={f.write_in} maxLength={100}
              onChange={(e) => set("write_in")(e.target.value)}/></Field>
        </Card>
        <Card title="Scoring">
          <Field label="Default points per question">
            <Input type="number" min="0.1" max="100" step="0.5" value={f.default_points}
              onChange={(e) => set("default_points")(e.target.value)}/></Field>
          <Field label="Critical questions worth more" hint="Ranges and singles · Q#:points">
            <Input value={f.weights} placeholder="e.g. 5:2, 9-12:3" spellCheck="false"
              onChange={(e) => set("weights")(e.target.value)}/></Field>
          <Field label="Partial credit for key-containing double marks"
            hint="Off sends double-marks to review; credit auto-awards the fraction.">
            <Segmented value={f.partial} onChange={set("partial")}
              options={[{ value: 0, label: "Off" }, { value: 0.25, label: "¼" },
                        { value: 0.5, label: "½" }, { value: 1, label: "Full" }]}/></Field>
        </Card>
        <Card title="Preview">
          {preview ? (
            <a href={preview} target="_blank" rel="noopener">
              <img src={preview} alt="Sheet preview"
                className="w-full cursor-zoom-in rounded border border-hair2"/></a>
          ) : <p className="text-[12px] text-ink3">Appears after you create the test.</p>}
        </Card>
      </div>
    </div>
  );
}
