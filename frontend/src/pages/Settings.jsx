import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CheckCircle2, Cpu, Download, Lightbulb, Lock, RotateCcw, Server,
         ShieldCheck, Wand2, Zap } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../App";
import { usePoll } from "../lib/hooks";
import { Badge, Button, Card, Field, Input, Segmented, Steps, Switch,
         useToast } from "../components/ui";

const GROUPS = {
  engine: { title: "OMR engine", sub: "Grid-relative thresholds (0 = empty sibling, 1 = printed ink).",
    defs: [
      ["t_fill", "Bubble fill threshold", 0.05, 0.8, 0.01,
        "Every bubble is scored 0 (unmarked paper) → 1 (printed ink). A bubble above this is read as filled."],
      ["t_blank", "Blank threshold", 0.02, 0.4, 0.01,
        "Below this a bubble is treated as empty. Raise it if stray specks read as marks."],
      ["faint_upper", "Faint-mark ceiling", 0.2, 0.95, 0.01,
        "A bubble between t_fill and this is still graded, but flagged for a quick human check."],
      ["multi_ratio", "Double-mark ratio", 0.3, 0.95, 0.01,
        "How close a runner-up bubble must be to the top before it's a double-mark. Lower = more strict."],
      ["dark_threshold_offset", "Binarisation offset", -60, 60, 1,
        "Shifts the darkness cut-off. Lower it to read faint pencil in low light; raise it to ignore light noise."],
      ["warp_width_px", "Flatten width (px)", 1000, 2400, 20,
        "Resolution of the flattened page before reading. Higher = slower but finer detail."],
    ]},
  camera: { title: "Camera & upload", sub: "Phone-side capture quality.",
    defs: [["jpeg_quality", "JPEG quality", 60, 100, 1,
            "Upload compression. Lower = smaller upload (fits flaky Wi-Fi)."],
           ["target_width_px", "Capture width (px)", 1280, 4096, 64,
            "Requested capture resolution from the phone camera."]]},
  server: { title: "Local server", sub: "Restart the server after changing these.",
    defs: [["port", "HTTP port", 1024, 65535, 1,
            "LAN port for the non-secure scan link."],
           ["https_port", "HTTPS port", 1024, 65535, 1,
            "HTTPS bridge port — needed for the live in-page camera."],
           ["max_upload_mb", "Max upload (MB)", 5, 100, 1,
            "Reject photos larger than this."]]},
};

/* One-tap bundles of thresholds for common pen / light conditions. */
const OMR_PRESETS = [
  ["Ballpoint (default)", { t_fill: 0.34, t_blank: 0.14, faint_upper: 0.65,
    multi_ratio: 0.62, dark_threshold_offset: 0 }],
  ["Pencil (lighter)", { t_fill: 0.30, t_blank: 0.12, faint_upper: 0.60,
    multi_ratio: 0.60, dark_threshold_offset: -6 }],
  ["Low light / torch", { t_fill: 0.32, t_blank: 0.13, faint_upper: 0.62,
    multi_ratio: 0.62, dark_threshold_offset: -12 }],
  ["High contrast / soft pencil", { t_fill: 0.42, t_blank: 0.20, faint_upper: 0.72,
    multi_ratio: 0.58, dark_threshold_offset: 4 }],
];
const TOGGLES = [
  ["auto_accept_blank", "Auto-accept blanks", "Blank = wrong without review."],
  ["master_csv", "Master CSV", "Also append to one combined file."],
];

function SliderRow({ k, label, lo, hi, step, val, save, hint }) {
  const [v, setV] = useState(val);
  useEffect(() => setV(val), [val]);
  return (
    <div className="border-b border-hair py-2.5 last:border-0">
      <div className="grid grid-cols-[minmax(0,1fr)_190px] items-center gap-4">
        <div className="min-w-0">
          <p className="text-[12px] font-bold">{label}
            <span className="tnum ml-2 font-extrabold text-brandhi">
              {+v % 1 === 0 ? +v : (+v).toFixed(2)}</span></p>
        </div>
        <input type="range" min={lo} max={hi} step={step} value={v}
          className="w-full accent-[var(--brand)]"
          onChange={(e) => setV(+e.target.value)}
          onMouseUp={() => save(k, v)}
          onTouchEnd={() => save(k, v)}
          onKeyUp={() => save(k, v)}/>
      </div>
      {hint && <p className="mt-1 text-[10.5px] leading-snug text-ink3">{hint}</p>}
    </div>
  );
}

const FLAG_LEGEND = [
  ["BLANK", "No bubble filled. Counts as wrong — but auto-accepted (no review) unless “Auto-accept blanks” is off.", "text-ink3"],
  ["FAINT", "A mark was found but weak or patchy. Graded normally, but held for a quick look so a half-erased answer isn't missed.", "text-amber"],
  ["MULTI", "More than one bubble looks filled. Nothing is awarded until a human picks the right one.", "text-err"],
];

function BubbleCheckGuide() {
  const [open, setOpen] = useState(false);
  return (
    <Card title="How bubble checking works" sub="What the flags mean and when a bubble is auto-accepted."
      right={<Button variant="ghost" icon={Lightbulb} onClick={() => setOpen(o => !o)}>
        {open ? "Hide" : "Learn"}</Button>}>
      <div className={`grid gap-4 overflow-hidden transition-all duration-300 ${open ? "" : "max-h-0 opacity-0"}`}>
        <div className="space-y-2">
          <p className="text-[11.5px] leading-relaxed text-ink2">
            The OMR engine first flattens the photo to a fixed grid, then scores every bubble
            from <b>0</b> (blank paper) to <b>1</b> (fully printed ink) relative to its empty
            sibling bubbles. Three numbers decide what happens next:
          </p>
          <ul className="space-y-1.5">
            <li className="flex gap-2 text-[11.5px]">
              <b className="tnum text-brandhi">t_blank</b>
              <span className="text-ink2">Below this = <b>empty</b>. Raise it to shrug off dust specks.</span></li>
            <li className="flex gap-2 text-[11.5px]">
              <b className="tnum text-brandhi">t_fill</b>
              <span className="text-ink2">Above this = a <b>selected</b> answer.</span></li>
            <li className="flex gap-2 text-[11.5px]">
              <b className="tnum text-brandhi">faint_upper</b>
              <span className="text-ink2">Between t_fill and this = still graded, but flagged so you
                can eyeball it (the <b>Review</b> queue).</span></li>
          </ul>
        </div>
        <div className="space-y-1.5">
          {FLAG_LEGEND.map(([f, d, tone]) => (
            <div key={f} className="flex gap-2 text-[11.5px]">
              <b className={`tnum shrink-0 rounded px-1.5 py-0.5 text-[10px] ${tone === "text-amber" ? "bg-amberdim text-amber" : tone === "text-err" ? "bg-errdim text-err" : "bg-base text-ink3"}`}>{f}</b>
              <span className="text-ink2">{d}</span></div>))}
        </div>
        <div className="rounded border border-hair bg-base p-2.5 text-[11px] leading-snug text-ink2">
          <b className="block text-[10px] font-extrabold uppercase tracking-[.12em] text-ink3">
            Auto-accept rule</b>
          A single clean bubble above <b>t_fill</b> and below a confident cap is scored instantly and
          <b> never</b> goes to review. Only <b>faint</b>, <b>double-marked</b> or <b>blank</b>
          answers are held — so you only ever look at the genuinely ambiguous bubbles.
        </div>
      </div>
      <div className="text-[10.5px] text-ink3">“Review” pauses on: faint marks · double/multiple marks · blanks.</div>
    </Card>
  );
}

function OmrPresets({ onApplied }) {
  const toast = useToast();
  const [busy, setBusy] = useState(null);
  const apply = async (name, vals) => {
    setBusy(name);
    try {
      await api("/api/settings", { method: "POST", body: JSON.stringify(vals) });
      toast(`Applied “${name}”`, "ok"); onApplied(true);
    } catch (e) { toast(e.message, "err"); }
    setBusy(null);
  };
  return (
    <Card title="One-tap presets" sub="Threshold bundles for common pen and light conditions."
      right={<Wand2 size={15} className="text-brandhi"/>}>
      <div className="grid grid-cols-2 gap-2">
        {OMR_PRESETS.map(([name, vals]) => (
          <Button key={name} variant="ghost" loading={busy === name}
            onClick={() => apply(name, vals)}>{name}</Button>))}
      </div>
      <p className="mt-2 text-[10.5px] leading-snug text-ink3">
        Presets pick sensible <b>t_fill</b>, <b>t_blank</b>, <b>faint_upper</b>,
        <b> multi_ratio</b> and the binarisation offset together. Apply one, then nudge
        individual sliders for your pen and light.</p>
    </Card>
  );
}

function HttpsWizard() {
  const toast = useToast();
  const { data: s, refresh } = usePoll("/api/https/status", { ms: 1200, active: true });
  const { data: cfg, refresh: rcfg } = usePoll("/api/settings", { ms: 15000 });
  const [busy, setBusy] = useState(false);
  const mode = cfg?.https_mode || "local";
  const save = (k, v) => api("/api/settings", { method: "POST",
    body: JSON.stringify({ [k]: v }) }).then(() => rcfg(true));
  const state = s?.state || "idle";
  return (
    <Card title="Live camera (HTTPS)" right={
      s?.serving_trusted ? <Badge tone="ok"><ShieldCheck size={11}/>active</Badge> : null}
      sub="Browsers only allow the in-page camera on HTTPS. Trusted = users need
           zero setup (one free duckdns.org domain). Offline = certificate once.">
      <Field label="Mode">
        <Segmented value={mode} onChange={(v) => save("https_mode", v)}
          options={[{ value: "letsencrypt", label: "Trusted · recommended" },
                    { value: "local", label: "Offline (local CA)" }]}/></Field>
      {(s?.serving_trusted || state === "ok") && cfg?.acme_domain ? (
        <div className="mb-3 flex items-center gap-2 rounded bg-okdim px-3 py-2 text-[12px]
          font-bold text-ok">
          <CheckCircle2 size={14}/> Live camera active — {cfg.acme_domain}
          {s?.cert_days_left > 0 ? ` · valid ${s.cert_days_left} more days` : ""}
        </div>
      ) : state === "error" && (
        <div className="mb-3 rounded bg-errdim px-3 py-2 text-[11.5px] leading-snug text-err">
          Setup failed — {s?.error}. Fix the hint below and press Start again.</div>
      )}
      <div className="mb-3 space-y-3">
        <Field label="Your free DuckDNS domain" hint="Create at duckdns.org and point it at this PC's LAN IP.">
          <Input defaultValue={cfg?.acme_domain || ""} key={cfg?.acme_domain}
            placeholder="myclass.duckdns.org" spellCheck="false"
            onBlur={(e) => save("acme_domain", e.target.value.trim())}/></Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="DuckDNS token">
            <Input defaultValue={cfg?.duckdns_token || ""} key={cfg?.duckdns_token}
              placeholder="paste your token" spellCheck="false"
              onBlur={(e) => save("duckdns_token", e.target.value.trim())}/></Field>
          <Field label="Email (expiry notices)">
            <Input defaultValue={cfg?.acme_email || ""} key={cfg?.acme_email}
              placeholder="you@school.edu" spellCheck="false"
              onBlur={(e) => save("acme_email", e.target.value.trim())}/></Field>
        </div>
        <Button className="w-full" icon={Zap} loading={busy || state === "running"}
          disabled={state === "running"}
          onClick={async () => {
            setBusy(true);
            try {
              await api("/api/https/provision", { method: "POST" });
              refresh();
            } catch (e) { toast(e.message, "err"); }
            setBusy(false);
          }}>
          {state === "running" ? "Setting up… follow the steps"
            : state === "error" ? "Try again" : "Set up the live camera"}</Button>
        {state === "running" && s?.steps?.length ? <Steps steps={s.steps}/> : null}
        <p className="text-center text-[10.5px] text-ink3">
          Takes 2–3 minutes, once. Internet is only needed during setup.</p>
      </div>
    </Card>
  );
}

function SystemCard() {
  const { data: s } = usePoll("/api/system", { ms: 10000 });
  const toast = useToast();
  const [out, setOut] = useState(null);
  if (!s) return null;
  const tile = (k, v) => (
    <div key={k} className="min-w-0 rounded border border-hair bg-base p-2.5">
      <span className="block text-[9px] font-extrabold uppercase tracking-[.12em]
        text-ink3">{k}</span>
      <b className="block truncate text-[12px]">{v}</b></div>);
  return (
    <Card title="System" sub="Version, environment and diagnostics."
      right={<Button variant="ghost" icon={CheckCircle2}
        onClick={async () => {
          setOut("running the self-test…");
          try {
            const r = await api("/api/selftest", { method: "POST" });
            setOut((r.ok ? "✔ ALL GREEN\n\n" : "✕ FAILURES\n\n") + r.tail);
          } catch { setOut("run  python selftest.py  in a terminal instead"); }
        }}>Run self-test</Button>}>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2">
        {tile("App", "v" + s.app)}{tile("Python", s.python)}
        {tile("Platform", s.platform)}{tile("OpenCV", s.opencv)}
        {tile("Tests", s.tests)}{tile("Data", s.data_mb + " MB")}
        {tile("HTTP", s.server.http ? `running :${s.server.port}` : "stopped")}
        {tile("HTTPS", s.server.https_domain ? s.server.https_domain
          : s.server.https ? "local CA" : "off")}
        {tile("Sheets", s.stats.sheets_received)}{tile("Graded", s.stats.auto_graded)}
        {tile("Flagged", s.stats.flagged)}{tile("Rejected", s.stats.rejected)}
      </div>
      {out && <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded
        border border-hair bg-base p-2.5 font-mono text-[10.5px]">{out}</pre>}
    </Card>
  );
}

export default function Settings() {
  const toast = useToast();
  const { data: s, refresh } = usePoll("/api/settings", { ms: 6000 });
  const save = (k, v) => api("/api/settings", { method: "POST",
    body: JSON.stringify({ [k]: v }) }).then(() => refresh(true));
  const fileRef = React.useRef(null);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        {Object.entries(GROUPS).map(([k, g]) => (
          <Card key={k} title={g.title} sub={g.sub}>
            {g.defs.map(([key, label, lo, hi, step, hint]) => (
              <SliderRow key={key} k={key} label={label} lo={lo} hi={hi} step={step}
                hint={hint} val={s?.[key]} save={save}/>))}
            {k === "engine" && <OmrPresets onApplied={refresh}/>}
            {k === "engine" && TOGGLES.map(([key, label, hint]) => (
              <div key={key} className="flex items-center gap-3 border-t border-hair py-2.5">
                <Switch checked={!!s?.[key]} label={label}
                  onChange={(v) => save(key, v)}/>
                <div className="min-w-0"><p className="text-[12px] font-bold">{label}</p>
                  <p className="text-[10.5px] text-ink3">{hint}</p></div>
              </div>))}
          </Card>
        ))}
      </div>
      <div className="space-y-4">
        <BubbleCheckGuide/>
        <HttpsWizard/>
        <SystemCard/>
        <Card title="Maintenance" sub="Data folder + backup/restore utilities.">
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" icon={RotateCcw}
              onClick={async () => {
                await api("/api/settings", { method: "POST",
                  body: JSON.stringify({ t_fill: 0.34, t_blank: 0.14, faint_upper: 0.65,
                    multi_ratio: 0.62, dark_threshold_offset: 0, warp_width_px: 1600,
                    auto_accept_blank: false, master_csv: true })});
                toast("Defaults restored", "ok"); refresh(true);
              }}>Reset to defaults</Button>
            <Button variant="ghost" icon={Download} onClick={() => fileRef.current?.click()}>
              Restore archive</Button>
            <input ref={fileRef} type="file" accept=".optibubble,.zip" className="hidden"
              onChange={async (e) => {
                const f = e.target.files[0]; e.target.value = "";
                if (!f) return;
                const pw = prompt("Archive password (leave empty if none):");
                if (pw == null) return;
                const fd = new FormData();
                fd.append("file", f); fd.append("password", pw);
                try {
                  const r = await api("/api/archive/restore", { method: "POST", body: fd });
                  toast(`Restored ${r.test_id} (${r.files} files)`, "ok");
                } catch (err) { toast(err.message, "err"); }
              }}/>
            <Button variant="ghost" icon={Server}
              onClick={() => api("/api/reveal", { method: "POST" }).catch(() => {})}>
              Open data folder</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
