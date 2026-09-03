import React, { createContext, useContext, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  CircleHelp, CircleUser, FileText, Home, Moon, Pencil, Radio, Settings2,
  Sun, Table2, ListChecks, ScanLine,
} from "lucide-react";
import { spring } from "./components/ui";
import { usePoll } from "./lib/hooks";
import { ToastHost, Badge } from "./components/ui";
import Dashboard from "./pages/Dashboard";
import Setup from "./pages/Setup";
import Serve from "./pages/Serve";
import Review from "./pages/Review";
import Results from "./pages/Results";
import Settings from "./pages/Settings";
import Help from "./pages/Help";
import Scanner from "./pages/Scanner";

export const AppState = createContext(null);
export const useApp = () => useContext(AppState);
const SYS = ["dashboard", "settings", "help"];
const TEST_TABS = [
  ["setup", "New test", Pencil], ["serve", "Scan & Serve", ScanLine],
  ["review", "Review", ListChecks], ["results", "Results", Table2],
];

function Shell({ page, goto, state, engineError, children }) {
  const [paper, setPaper] = useState(
    () => localStorage.getItem("ob_theme") === "day");
  useEffect(() => {
    document.documentElement.className = paper ? "theme-day" : "theme-ink";
    localStorage.setItem("ob_theme", paper ? "day" : "ink");
  }, [paper]);
  const t = state?.test;
  const pending = state?.stats?.pending_review || 0;
  const sys = SYS.includes(page);
  const httpsDomain = state?.server?.https_domain;
  return (
    <div className="grid h-full min-w-0 grid-rows-[48px_minmax(0,1fr)]
      md:grid-cols-[minmax(0,224px)_minmax(0,1fr)] md:grid-rows-[48px_minmax(0,1fr)]">
      {/* title bar — traffic lights · wordmark · engine status */}
      <div className="flex min-w-0 items-center gap-3 border-b border-hair
        bg-[var(--bg1)] px-4">
        <span className="regmark regmark-iris shrink-0" aria-hidden="true" />
        <span className="mx-auto flex min-w-0 items-center gap-2 font-mono
          text-[10px] uppercase tracking-[.2em] text-ink3">
          OPTIBubble
          {t && <span className="tnum text-ink2">· {t.test_id}</span>}
        </span>
        <span className={`ml-auto hidden shrink-0 items-center gap-1.5 font-mono
          text-[10px] uppercase tracking-[.2em] sm:flex
          ${state?.server?.running ? "text-ok" : "text-ink3"}`}>
          <i className={`h-1.5 w-1.5 rounded-full bg-current
            ${state?.server?.running ? "livedot" : ""}`}/>
          {httpsDomain ? "session live" : state?.server?.running
            ? "engine ready" : "engine idle"}
        </span>
      </div>

      {/* test topbar */}
      <AnimatePresence>
        {!sys && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 48, opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={spring}
            className="flex min-w-0 items-center gap-3 overflow-hidden border-b
              border-hair bg-[var(--bg1)] px-3">
            <span className="hidden shrink-0 text-[9px] font-extrabold uppercase
              tracking-[.2em] text-ink3 lg:block">Test</span>
            {t ? (
              <span className="flex min-w-0 items-center gap-2 rounded-full bg-fill
                px-3 py-1 text-[11.5px] font-bold text-ink2">
                <FileText size={12} className="shrink-0 text-brandhi"/>
                <span className="truncate">{t.title}</span>
                <span className="tnum shrink-0 text-ink3">{t.test_id}</span>
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-[11.5px] font-semibold text-warn">
                <CircleUser size={13}/> no active test
              </span>
            )}
            <nav className="flex min-w-0 items-center gap-0.5 overflow-x-auto"
              style={{ scrollbarWidth: "none" }}>
              {TEST_TABS.map(([id, label, Icon]) => (
                <button key={id} data-testid={`nav-${id}`} onClick={() => goto(id)}
                  className={`focusable relative flex shrink-0 items-center gap-1.5 px-3
                    py-2 text-[12px] font-bold ${page === id ? "text-brand" : "text-ink2 hov"}`}>
                  <Icon size={13}/><span className="hidden sm:inline">{label}</span>
                  {id === "review" && pending > 0 && (
                    <span className="rounded-full bg-warn px-1.5 text-[10px]
                      font-extrabold text-[#1F2937]">{pending}</span>)}
                  {page === id && <motion.span layoutId="tabline" transition={spring}
                    className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-brand"/>}
                </button>
              ))}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>

      {/* system sidebar */}
      <nav className={`row-start-2 flex flex-col gap-0.5 overflow-y-auto border-r
        border-hair bg-[var(--bg1)] p-2.5 ${sys ? "" : "hidden md:flex"}`}>
        <p className="px-2.5 pb-1.5 pt-1 text-[9px] font-extrabold uppercase
          tracking-[.2em] text-ink3">System</p>
        {[["dashboard", "Dashboard", Home], ["settings", "Settings", Settings2],
          ["help", "Help & FAQ", CircleHelp]].map(([id, label, Icon]) => (
          <button key={id} data-testid={`nav-${id}`} onClick={() => goto(id)}
            className={`focusable hov relative flex items-center gap-2.5 rounded px-2.5
              py-2 text-[12.5px] font-bold ${page === id ? "text-brand" : "text-ink2"}`}>
            {page === id && <motion.span layoutId="navline" transition={spring}
              className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2
                rounded-r bg-brand"/>}
            <Icon size={15} className="shrink-0"/><span>{label}</span>
          </button>
        ))}
        <div className="mt-auto space-y-2 px-1 pt-3">
          <div className="flex min-w-0 items-center gap-1.5">
            <span className={`min-w-0 flex-1 truncate rounded-full px-2.5 py-1
              text-[9.5px] font-extrabold uppercase tracking-[.08em]
              ${state?.server?.running ? "bg-okdim text-ok" : "bg-fill text-ink3"}`}>
              {httpsDomain ? `https ${httpsDomain}`
                : state?.server?.running ? `online :${state.server.port}` : "offline"}
            </span>
            <button onClick={() => setPaper((p) => !p)} aria-label="Toggle theme"
              className="focusable hov flex h-7 w-7 items-center justify-center rounded text-ink2">
              {paper ? <Sun size={14}/> : <Moon size={14}/>}
            </button>
          </div>
          <p className="text-[10px] leading-relaxed text-ink3">
            v{state?.version || "…"} · local only<br/>
            <span className="break-all">{state?.data_dir}</span>
          </p>
        </div>
      </nav>

      {/* main */}
      <main className="row-start-2 min-w-0 overflow-y-auto p-5 md:p-6"
        data-testid="main">
        {engineError && (
          <div role="alert" className="mb-4 flex items-center gap-2 rounded
            border border-err/40 bg-errdim px-3 py-2 font-mono text-[10.5px]
            uppercase tracking-[.14em] text-err">
            <span className="livedot h-1.5 w-1.5 rounded-full bg-current"/>
            engine unreachable — {error.message || "restart the app or check the port"}
          </div>)}
        <AnimatePresence mode="wait">
          <motion.div key={page} className="mx-auto max-w-[1180px]"
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
  const [page, setPage] = useState(
    window.__OB_ROUTE__ === "scanner"
      || window.location.pathname.startsWith("/scan/")
      ? "scanner" : "dashboard");
  const { data: state, error, refresh } = usePoll("/api/state", { ms: 2000 });
  const goto = (p) => { setPage(p); };
  const ctx = { state, error, refresh, goto };
  return (
    <AppState.Provider value={ctx}>
      <ToastHost>
        {page === "scanner"
          ? <Scanner/>
          : <Shell page={page} goto={goto} state={state} engineError={error}>
              {page === "dashboard" && <Dashboard/>}
              {page === "setup" && <Setup/>}
              {page === "serve" && <Serve/>}
              {page === "review" && <Review/>}
              {page === "results" && <Results/>}
              {page === "settings" && <Settings/>}
              {page === "help" && <Help/>}
            </Shell>}
      </ToastHost>
    </AppState.Provider>
  );
}
