import React, { createContext, useContext, useEffect, useState, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  CircleHelp, FolderOpen, Home, ListChecks, Moon, Radio, Settings2,
  Table2, Sun, Menu, Search,
} from "lucide-react";
import { spring, ToastHost } from "./components/ui";
import { usePoll } from "./lib/hooks";
import Dashboard from "./pages/Dashboard";
import Setup from "./pages/Setup";
import Serve from "./pages/Serve";
import Review from "./pages/Review";
import Results from "./pages/Results";
import Settings from "./pages/Settings";
import Help from "./pages/Help";
import Scanner from "./pages/Scanner";
import TestList from "./pages/TestList";

export const AppState = createContext(null);
export const useApp = () => useContext(AppState);

const NAV = [
  ["dashboard", "Dashboard", Home],
  ["session", "Session", Radio],
  ["tests", "Tests", FolderOpen],
  ["review", "Review", ListChecks],
  ["results", "Results", Table2],
];
const SYS = [
  ["settings", "Settings", Settings2],
  ["help", "Help & FAQ", CircleHelp],
];
const ALL = [...NAV, ...SYS];

/* brand wordmark in the bundled display face */
function BrandMark() {
  return (
    <span className="flex shrink-0 items-center gap-2.5">
      <span className="regmark regmark-iris shrink-0" aria-hidden="true" />
      <span className="fbrand whitespace-nowrap text-[17px] leading-none"
        style={{ color: "var(--tx)" }}>
        OPTIBubble</span>
    </span>
  );
}

/* Cmd/Ctrl+K quick-jump palette (Watermelon/Kokonut-style) */
function CommandPalette({ onJump }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const inputRef = useRef(null);
  useEffect(() => {
    const h = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault(); setOpen((o) => !o); setQ(""); setIdx(0);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 20);
  }, [open]);
  const items = ALL.filter(([id, label]) => label.toLowerCase().includes(q.toLowerCase()));
  useEffect(() => setIdx(0), [q]);
  return (
    <>
      <button onClick={() => setOpen(true)}
        className="focusable hov hidden w-full items-center gap-2 rounded-lg border
          border-hair bg-[var(--bg3)] px-3 py-2 text-[12px] text-ink3 sm:flex">
        <Search size={13} /> Jump to…
        <span className="ml-auto flex items-center gap-0.5 font-mono text-[10px]">
          <kbd>⌘</kbd><kbd>K</kbd></span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-[400] flex items-start justify-center
            pt-[16vh] p-6"
            style={{ background: "rgba(20,25,33,.5)", backdropFilter: "blur(4px)" }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}>
            <motion.div initial={{ opacity: 0, scale: 0.97, y: -6 }}
              animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.97 }}
              transition={spring}
              className="panel grain w-full max-w-[440px] overflow-hidden p-0">
              <div className="flex items-center gap-2.5 border-b border-hair px-4 py-3">
                <Search size={15} className="text-ink3" />
                <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(items.length - 1, i + 1)); }
                    else if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(0, i - 1)); }
                    else if (e.key === "Enter" && items[idx]) {
                      onJump(items[idx][0]); setOpen(false);
                    }
                  }}
                  placeholder="Jump to a page…"
                  className="min-w-0 flex-1 bg-transparent text-[13.5px] text-ink
                    outline-none placeholder:text-ink3" />
                <kbd>esc</kbd>
              </div>
              <ul className="max-h-[320px] overflow-y-auto p-2">
                {items.length ? items.map(([id, label, Icon], i) => (
                  <li key={id}>
                    <button onClick={() => { onJump(id); setOpen(false); }}
                      onMouseEnter={() => setIdx(i)}
                      className={`flex w-full items-center gap-2.5 rounded-lg px-3
                        py-2.5 text-left text-[13px] font-bold ${i === idx
                          ? "bg-branddim text-brand" : "text-ink2 hover:bg-[var(--bg3)]"}`}>
                      <Icon size={15} className="shrink-0" />
                      <span className="min-w-0 truncate">{label}</span>
                    </button>
                  </li>
                )) : <li className="px-3 py-6 text-center text-[12.5px] text-ink3">
                    No matches.</li>}
              </ul>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function Shell({ page, goto, state, engineError, children }) {
  const [night, setNight] = useState(
    () => localStorage.getItem("ob_theme") === "ink");
  useEffect(() => {
    document.documentElement.className = night ? "theme-ink" : "theme-day";
    localStorage.setItem("ob_theme", night ? "ink" : "day");
  }, [night]);
  const t = state?.test;
  const pending = state?.stats?.pending_review || 0;
  const httpsDomain = state?.server?.https_domain;
  const [railOpen, setRailOpen] = useState(false);

  return (
    <div className="grid h-full min-w-0 grid-rows-[56px_minmax(0,1fr)]
      lg:grid-cols-[240px_minmax(0,1fr)] lg:grid-rows-[56px_minmax(0,1fr)]">
      {/* title bar */}
      <div className="flex min-w-0 items-center gap-3 border-b border-hair
        bg-[var(--bg1)] px-4 lg:col-span-2">
        <BrandMark />
        <div className="ml-auto flex min-w-0 items-center gap-3">
          <span className={`flex min-w-0 items-center gap-1.5 text-[11px]
            font-bold ${state?.server?.running ? "text-ok" : "text-ink3"}`}>
            <i className={`h-2 w-2 shrink-0 rounded-full bg-current
              ${state?.server?.running ? "livedot" : ""}`} />
            <span className="truncate">
              {state?.server?.running
                ? (httpsDomain ? `session live · ${httpsDomain}`
                  : `engine ready · :${state.server.port}`)
                : "engine idle"}</span>
          </span>
          <button onClick={() => setNight((n) => !n)} aria-label="Toggle theme"
            className="focusable hov flex h-8 w-8 shrink-0 items-center justify-center
              rounded text-ink2">{night ? <Sun size={15} /> : <Moon size={15} />}</button>
        </div>
      </div>

      {/* rail */}
      <nav className={`row-start-2 flex flex-col gap-0.5 overflow-y-auto border-r
        border-hair bg-[var(--bg1)] p-3 ${railOpen ? "flex" : "max-lg:hidden"}`}>
        {t ? (
          <div className="mb-2 rounded-xl border border-hair bg-[var(--bg2)] p-3">
            <p className="mb-1 text-[10px] font-extrabold uppercase tracking-[.12em]
              text-ink3">Active test</p>
            <b className="block truncate text-[13px] text-ink">{t.title}</b>
            <p className="tnum font-mono text-[10.5px] text-ink3">
              {t.test_id} · {t.num_questions}×{t.options_per_question}</p>
          </div>
        ) : (
          <div className="mb-2 rounded-xl border border-dashed border-hair2 p-3
            text-[12px] font-semibold text-ink3">No active test</div>
        )}

        <div className="mb-3"><CommandPalette onJump={goto} /></div>

        <p className="px-2.5 pb-1.5 text-[10px] font-extrabold uppercase
          tracking-[.12em] text-ink3">Classroom</p>
        {NAV.map(([id, label, Icon]) => (
          <button key={id} data-testid={`nav-${id}`} onClick={() => goto(id)}
            className={`focusable hov flex items-center gap-2.5 rounded-lg px-3
              py-2.5 text-[13px] font-bold ${page === id ? "bg-branddim text-brand"
                : "text-ink2"}`}>
            <Icon size={16} className="shrink-0" />
            <span className="min-w-0 flex-1 truncate">{label}</span>
            {id === "review" && pending > 0 && (
              <span className="rounded-full bg-warn px-1.5 text-[10px]
                font-extrabold text-[#22170a]">{pending}</span>)}
          </button>
        ))}

        <div className="my-3 h-px bg-hair" />
        <p className="px-2.5 pb-1.5 text-[10px] font-extrabold uppercase
          tracking-[.12em] text-ink3">System</p>
        {SYS.map(([id, label, Icon]) => (
          <button key={id} data-testid={`nav-${id}`} onClick={() => goto(id)}
            className={`focusable hov flex items-center gap-2.5 rounded-lg px-3
              py-2.5 text-[13px] font-bold ${page === id ? "bg-branddim text-brand"
                : "text-ink2"}`}>
            <Icon size={16} className="shrink-0" /><span>{label}</span>
          </button>
        ))}

        <div className="mt-auto space-y-2 px-1 pt-3">
          <p className="text-[11px] leading-relaxed text-ink3">
            v{state?.version || "…"} · local only</p>
          <p className="break-all text-[10.5px] text-ink3">{state?.data_dir}</p>
        </div>
      </nav>

      {/* mobile rail toggle */}
      <button onClick={() => setRailOpen((o) => !o)}
        className="row-start-2 mt-3 hidden max-lg:flex justify-self-center
          items-center gap-1.5 rounded-full border border-hair bg-[var(--bg1)]
          px-4 py-1.5 text-[12px] font-bold text-ink2">
        <Menu size={14} className={railOpen ? "" : "rotate-180"} /> Menu</button>

      {/* main */}
      <main className="row-start-2 min-w-0 overflow-y-auto p-5 md:p-7"
        data-testid="main">
        {engineError && (
          <div role="alert" className="mb-4 flex items-center gap-2 rounded-xl
            border border-err/40 bg-errdim px-3 py-2.5 text-[12px] font-bold
            text-err">
            <span className="livedot h-2 w-2 rounded-full bg-current" />
            engine unreachable — {engineError.message || "restart the app or check the port"}
          </div>)}
        <AnimatePresence mode="wait">
          <motion.div key={page} className="mx-auto max-w-[1240px]"
            initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.16, ease: "easeOut" }}>
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

export default function App() {
  const isScanner = window.__OB_ROUTE__ === "scanner"
    || window.location.pathname.startsWith("/scan/");
  const [page, setPage] = useState(isScanner ? "scanner" : "dashboard");
  const { data: state, error, refresh } = usePoll("/api/state", { ms: 2000 });
  const goto = (p) => { setPage(p); };
  const ctx = { state, error, refresh, goto };
  return (
    <AppState.Provider value={ctx}>
      <ToastHost>
        {page === "scanner"
          ? <Scanner />
          : <Shell page={page} goto={goto} state={state} engineError={error}>
              {page === "dashboard" && <Dashboard />}
              {page === "setup" && <Setup />}
              {page === "session" && <Serve />}
              {page === "tests" && <SetupLibrary />}
              {page === "review" && <Review />}
              {page === "results" && <Results />}
              {page === "settings" && <Settings />}
              {page === "help" && <Help />}
            </Shell>}
      </ToastHost>
    </AppState.Provider>
  );
}

/* Tests library (the old test-management page) lives under its own nav item. */
function SetupLibrary() { return <TestList />; }
