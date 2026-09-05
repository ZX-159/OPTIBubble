/* Ledger UI kit — every component carries the full state matrix:
   idle · hover (pointer) · focus-visible (keyboard) · active · disabled ·
   loading · success · error. Motion springs throughout. */
import React, { createContext, useContext, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle, Check, Info, Loader2, X } from "lucide-react";

export const spring = { type: "spring", stiffness: 480, damping: 34, mass: 0.9 };
export const softSpring = { type: "spring", stiffness: 260, damping: 30 };

/* ------------------------------------------------------------------ Button */
const BTN = {
  primary: "bg-brand text-brandink",
  ghost: "bg-[var(--bg3)] text-ink border border-hair2",
  danger: "bg-err text-white",
  ok: "bg-ok text-[#0B281B]",
};
export function Button({ variant = "primary", loading, success, icon: Icon,
                         children, className = "", ...rest }) {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!success) return;
    setDone(true);
    const t = setTimeout(() => setDone(false), 1400);
    return () => clearTimeout(t);
  }, [success]);
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      aria-busy={loading || undefined}
      className={`focusable btn-hov inline-flex items-center justify-center gap-2 rounded
        px-4 py-2 text-[13px] font-extrabold tracking-wide
        ${BTN[variant]} ${className}`}>
      {loading ? <Loader2 size={14} className="animate-spin" />
        : done ? <Check size={14} />
        : Icon ? <Icon size={14} /> : null}
      {done ? "Done" : children}
    </button>
  );
}

export function IconButton({ icon: Icon, label, tone = "default", className = "", ...rest }) {
  return (
    <button {...rest} title={label} aria-label={label}
      className={`focusable hov inline-flex h-8 w-8 items-center justify-center rounded
        text-ink2 ${tone === "danger" ? "hover:!bg-errdim hover:!text-err" : ""} ${className}`}>
      <Icon size={15} />
    </button>
  );
}

/* -------------------------------------------------------------------- Card */
export function Card({ title, sub, right, children, className = "", ...rest }) {
  return (
    <motion.section layout={false}
      className={`panel grain p-5 ${className}`}
      {...rest}>
      {(title || right) && (
        <div className="mb-3 flex min-w-0 items-center gap-3">
          {title && <h3 className="min-w-0 truncate text-[13.5px] font-extrabold
            tracking-[-0.005em] text-ink">{title}</h3>}
          <div className="ml-auto flex items-center gap-2">{right}</div>
        </div>
      )}
      {sub && <p className="-mt-2 mb-3 text-[12.5px] leading-relaxed text-ink3">{sub}</p>}
      {children}
    </motion.section>
  );
}

/* ------------------------------------------------------------------ Inputs */
export function Field({ label, hint, error, children }) {
  return (
    <label className="mb-3.5 block min-w-0">
      <span className="mb-1.5 block text-[12px] font-bold text-ink2">{label}</span>
      {children}
      {error
        ? <span className="mt-1.5 flex items-center gap-1.5 text-[12px] font-semibold text-err">
            <AlertTriangle size={12} />{error}</span>
        : hint && <span className="mt-1.5 block text-[12px] leading-snug text-ink3">{hint}</span>}
    </label>
  );
}
const inputCls = `focusable w-full rounded-lg bg-[var(--bg3)] px-3 py-2.5 text-[13.5px] text-ink
  placeholder:text-ink3 border border-transparent focus-visible:border-brand`;
export const Input = (p) => <input {...p} className={`${inputCls} ${p.className || ""}`} />;
export const Select = (p) => (
  <select {...p} className={`${inputCls} appearance-none ${p.className || ""}`} />
);
export const Textarea = (p) => <textarea {...p} className={`${inputCls} resize-y ${p.className || ""}`} />;

export function Segmented({ options, value, onChange, className = "" }) {
  return (
    <div role="radiogroup" className={`inline-flex max-w-full gap-0.5 rounded-lg bg-[var(--bg3)] p-0.5 ${className}`}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button key={String(o.value)} role="radio" aria-checked={active} type="button"
            onClick={() => onChange(o.value)}
            className={`focusable relative min-w-0 flex-1 overflow-hidden
              text-ellipsis whitespace-nowrap rounded px-3 py-2 text-[12.5px]
              font-bold ${active ? "text-brandink" : "text-ink3 hov"}`}>
            {active && <motion.span layoutId={`seg-${options.map(x=>x.value).join()}`}
              className="absolute inset-0 rounded-[6px] bg-brand"
              transition={spring} />}
            <span className="relative z-10 block min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export function Switch({ checked, onChange, label }) {
  return (
    <button role="switch" aria-checked={checked} aria-label={label} type="button"
      onClick={() => onChange(!checked)}
      className={`focusable relative h-5 w-9 shrink-0 rounded-full transition-colors
        ${checked ? "bg-brand" : "bg-[var(--bg3)] border border-hair2"}`}>
      <motion.span layout transition={spring}
        className={`absolute top-[3px] h-3.5 w-3.5 rounded-full
          ${checked ? "right-[3px] bg-brandink" : "left-[3px] bg-ink3"}`} />
    </button>
  );
}

/* ------------------------------------------------------------------ Badges */
const TONES = { ok: "bg-okdim text-ok", warn: "bg-warndim text-warn",
                err: "bg-errdim text-err", info: "bg-branddim text-brand",
                mute: "bg-[var(--bg3)] text-ink3" };
export const Badge = ({ tone = "mute", children, className = "" }) => (
  <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1
    text-[11px] font-bold ${TONES[tone]}
    ${className}`}>
    {children}</span>
);
export const LiveBadge = ({ tone = "ok", children }) => (
  <Badge tone={tone}><span className="livedot h-1.5 w-1.5 rounded-full bg-current"/>{children}</Badge>
);

/* ------------------------------------------------------------------ States */
export const Skeleton = ({ className = "" }) => <div className={`skeleton ${className}`} />;
export function EmptyState({ icon: Icon, title, children }) {
  return (
    <div className="flex flex-col items-center gap-1.5 px-4 py-10 text-center">
      {Icon && <Icon size={30} className="text-ink3" />}
      <b className="text-[14px] text-ink2">{title}</b>
      <div className="max-w-sm text-[12.5px] leading-relaxed text-ink3">{children}</div>
    </div>
  );
}
export function ErrorState({ error, onRetry, retrying }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-2 px-4 py-8 text-center">
      <AlertTriangle size={26} className="text-err" />
      <b className="text-[14px] text-err">Something went wrong</b>
      <p className="max-w-sm text-[12.5px] text-ink3">{String(error || "")}</p>
      {onRetry && <Button variant="ghost" loading={retrying} onClick={onRetry}>Try again</Button>}
    </div>
  );
}
export const Spinner = ({ size = 18, className = "" }) => (
  <Loader2 size={size} className={`animate-spin text-brand ${className}`} />);

/* ------------------------------------------------------------------ Modal */
export function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <motion.div className="fixed inset-0 z-[200] flex items-center justify-center p-6"
      style={{ background: "rgba(20,25,33,.55)", backdropFilter: "blur(4px)" }}
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <motion.div role="dialog" aria-modal="true" aria-label={title}
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.97 }} transition={spring}
        className={`panel grain max-h-[86vh] w-full overflow-y-auto p-6 shadow-pop ${wide ? "max-w-[720px]" : "max-w-[540px]"}`}>
        <div className="mb-3 flex items-center gap-3">
          <h3 className="min-w-0 flex-1 truncate text-[15px] font-extrabold text-ink">{title}</h3>
          <IconButton icon={X} label="Close" onClick={onClose} />
        </div>
        {children}
      </motion.div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ Toasts */
const ToastCtx = createContext(null);
export const useToast = () => useContext(ToastCtx);
export function ToastHost({ children }) {
  const [items, setItems] = useState([]);
  const push = (msg, tone = "info") => {
    const id = Math.random().toString(36).slice(2);
    setItems((t) => [...t, { id, msg, tone }]);
    setTimeout(() => setItems((t) => t.filter((x) => x.id !== id)), 3400);
  };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[300] flex flex-col gap-2">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div key={t.id}
              initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 24 }} transition={softSpring}
              className="pointer-events-auto flex max-w-sm items-start gap-2 rounded
                border-l-2 border bg-[var(--bg1)] px-3.5 py-2.5 text-[12.5px]
                font-bold shadow-pop
                ${t.tone === 'ok' ? 'border-ok' : t.tone === 'err' ? 'border-err' : 'border-brand'}"
              role="status">
              {t.tone === "ok" ? <Check size={14} className="mt-0.5 shrink-0 text-ok"/>
                : t.tone === "err" ? <AlertTriangle size={14} className="mt-0.5 shrink-0 text-err"/>
                : <Info size={14} className="mt-0.5 shrink-0 text-brand"/>}
              <span>{t.msg}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

/* ------------------------------------------------------------- AnimatedNum */
export function AnimatedNum({ value, className = "" }) {
  const [shown, setShown] = useState(value);
  const prev = useRef(value);
  useEffect(() => {
    const from = prev.current, to = value;
    prev.current = value;
    if (from === to) return;
    const t0 = performance.now(), dur = 420;
    let raf;
    const tick = (now) => {
      const k = Math.min(1, (now - t0) / dur);
      setShown(Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <span className={`tnum ${className}`}>{shown}</span>;
}

/* ------------------------------------------------------------- ProgressSteps */
export function Steps({ steps }) {
  return (
    <ol className="my-3">
      {steps.map((s) => (
        <li key={s.id} className={`flex items-start gap-2.5 py-1.5 text-[12.5px]
          ${s.status === "active" ? "text-ink" : s.status === "done" ? "text-ink2"
            : s.status === "error" ? "text-err" : "text-ink3"}`}>
          <span className={`mt-0.5 flex h-[18px] w-[18px] shrink-0 items-center
            justify-center rounded-full border
            ${s.status === "done" ? "border-ok bg-okdim text-ok"
              : s.status === "error" ? "border-err bg-errdim text-err"
              : s.status === "active" ? "livedot border-brand" : "border-hair2"}`}>
            {s.status === "done" ? <Check size={11} />
              : s.status === "error" ? <X size={11} /> : null}
          </span>
          <span className="min-w-0">
            <b className="font-bold">{s.label}</b>
            {s.detail && <span className="block text-[11.5px] text-ink3">{s.detail}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

/* ---------------------------------------------------------------- ConfBar */
export const ConfBar = ({ v }) => (
  <div className="h-[4px] w-16 overflow-hidden rounded bg-[var(--bg3)]">
    <motion.div className="h-full bg-brand" initial={{ width: 0 }}
      animate={{ width: `${Math.round(v * 100)}%` }} transition={softSpring} />
  </div>
);
