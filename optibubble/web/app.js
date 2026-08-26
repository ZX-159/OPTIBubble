/* ==========================================================================
   OPTIBubble desktop app — application logic (vanilla JS, zero dependencies)
   ========================================================================== */
"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

const PAGES = [
  ["dashboard", "⌂"], ["setup", "✎"], ["serve", "◉"], ["review", "☰"],
  ["results", "▦"], ["settings", "⚙"], ["help", "?"],
];
const FAQ = [
  ["How do students scan their sheets?",
   "Start the server on the Scan & Serve page. Students open the standard camera app on their phone, point it at the QR code, and the scanner page opens in their browser — no app install, no account, no internet. Everyone just needs to be on the same Wi-Fi network as this computer."],
  ["The phone shows a camera error / black view — why?",
   "Browsers only allow the live in-page camera on secure (HTTPS) or localhost pages. On a plain LAN address OPTIBubble automatically falls back to the phone's native camera app via the upload button — photos taken that way are graded exactly the same."],
  ["What pens or pencils work best?",
   "Black or dark blue ballpoint gives the highest confidence; dark pencils (2B) work too. Ask students to fill bubbles completely and erase cleanly — faint or half-erased marks are intentionally flagged for your review instead of being silently misgraded."],
  ["What gets flagged for review?",
   "Three situations: (1) no bubble filled — unanswered; (2) several bubbles filled — double-marked, invalid; (3) a mark whose darkness falls inside the ambiguity band — a faint mark or a partially erased one. You can tune all three thresholds in Settings → OMR engine, or auto-accept blanks to reduce review load."],
  ["A sheet was rejected — what now?",
   "The phone shows the exact reason and a hint. Common causes: a corner square hidden or cut off, the photo too dark or blurry, or a very steep angle. Flatten the sheet, avoid shadows, shoot from directly above, and include all four black corner squares."],
  ["Where is my data stored? (privacy)",
   "Everything stays on this computer — see the folder at the bottom of the sidebar. Each test keeps its PDF, every received photo, crop evidence and results.csv. Nothing is ever uploaded anywhere; the only network traffic is photos travelling over your own LAN from phones to this PC."],
  ["Can I print with any printer and paper?",
   "Yes — any inkjet or laser printer on plain A4 or US-Letter paper, printed at 100% scale (choose 'Actual size', not 'Fit to page')."],
  ["How many questions fit on one sheet?",
   "Up to 102 on a single A4 page (one to three columns of up to 34 rows), with 2–5 options each. Letter paper holds slightly fewer rows; the layout adapts automatically."],
  ["Can several phones scan at once?",
   "Yes — the server accepts simultaneous uploads and grades in parallel with two worker threads."],
  ["Does it work offline?",
   "Completely. The desktop app, grading engine, mobile page and even the fonts are all served from your machine over the local network."],
  ["How do I get results into Excel?",
   "Open the Results page → 'Export CSV copy'. The Detailed_Answers_JSON column contains the full per-question breakdown for deep dives."],
  ["The QR code doesn't open anything.",
   "Check that (1) the phone is on the same Wi-Fi, (2) your firewall allows Python/OPTIBubble on the configured port (default 5000), (3) the URL under the QR matches this computer's IP (switch the IP selector if you have several adapters). On some routers 'AP/client isolation' blocks phone→PC traffic — disable it in the router admin."],
  ["Can I run this as a native desktop app?",
   "Yes — the repo includes a Tauri 2 wrapper (src-tauri/). With Rust installed, run the commands in the README to get a native window and installers for Windows, macOS and Linux."],
];

/* ------------------------------------------------------------------ state */
const S = {
  state: null, page: "dashboard",
  key: {},                    // answer-key editor state {q: "A"}
  opts: 4, digits: 7, paper: "a4",
  reviewSel: null, reviewItems: [], overrides: {},
  lastLogLen: 0,
};

/* ------------------------------------------------------------------ toast */
function toast(msg, cls = "") {
  const t = document.createElement("div");
  t.className = "toast " + cls;
  t.textContent = msg;
  $("toasts").appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; t.style.transition = "opacity .3s"; }, 2600);
  setTimeout(() => t.remove(), 3000);
}
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw Object.assign(new Error("api"), { data, status: r.status });
  return data;
}

/* ------------------------------------------------------------- navigation */
function buildTabs() {
  $("tabs").innerHTML = PAGES.map(([id, ic]) =>
    `<button class="tab" data-page="${id}">${ic}<span>${labelOf(id)}</span>
     ${id === "review" ? '<span class="badge" id="tabReviewBadge">0</span>' : ""}</button>`
  ).join("");
}
const LABELS = {dashboard:"Dashboard", setup:"New Test", serve:"Scan & Serve",
  review:"Review", results:"Results", settings:"Settings", help:"Help"};
const labelOf = id => LABELS[id] || id;

function goto(page) {
  S.page = page;
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  $("page-" + page).classList.add("active");
  document.querySelectorAll(".nav a.item").forEach(a =>
    a.classList.toggle("active", a.dataset.page === page));
  document.querySelectorAll(".tab").forEach(t =>
    t.classList.toggle("active", t.dataset.page === page));
  if (page === "dashboard") renderDashboard();
  if (page === "serve") renderServe();
  if (page === "review") loadReview();
  if (page === "results") loadResults();
  if (page === "settings") loadSettings();
  if (page === "help") renderFaq();
}

/* -------------------------------------------------------------- dashboard */
function renderDashboard() {
  const st = S.state; if (!st) return;
  $("stReceived").textContent = st.stats.sheets_received;
  $("stGraded").textContent = st.stats.auto_graded;
  $("stPending").textContent = st.stats.pending_review;
  $("stExported").textContent = st.stats.exported;
  $("navReviewBadge").textContent = st.stats.pending_review;
  $("navReviewBadge").classList.toggle("show", st.stats.pending_review > 0);
  const tb = $("tabReviewBadge"); if (tb) { tb.textContent = st.stats.pending_review;
    tb.classList.toggle("show", st.stats.pending_review > 0); }

  if (st.test) {
    $("currentTestSub").textContent = "Session " + st.test.test_id;
    $("currentTestBody").innerHTML =
      `<b style="font-size:15px">${esc(st.test.title)}</b><br>
       <span class="muted">${esc(st.test.subject)} · ${st.test.num_questions} questions ·
       ${st.test.options_per_question} options · ${st.test.page_size.toUpperCase()}</span>`;
    $("pdfLink").style.display = "";
  } else {
    $("currentTestSub").textContent = "No test yet — create one to begin.";
    $("currentTestBody").textContent = "—";
    $("pdfLink").style.display = "none";
  }
  const rt = S.tests || [];
  $("recentTests").innerHTML = rt.length ? `<table class="tbl"><thead><tr>
      <th>Title</th><th>ID</th><th>Questions</th><th>Graded</th><th></th></tr></thead><tbody>` +
    rt.slice(0, 10).map(t => `<tr>
      <td><b>${esc(t.title)}</b>${st.test && t.test_id === st.test.test_id ?
        ' <span class="badge info">active</span>' : ""}</td>
      <td class="mono">${esc(t.test_id)}</td><td>${t.num_questions}</td><td>${t.graded || 0}</td>
      <td><button class="btn sm ghost" data-open="${esc(t.test_id)}">Open</button></td></tr>`).join("") +
    "</tbody></table>" : '<p class="muted">No saved tests yet.</p>';
  $("recentTests").querySelectorAll("[data-open]").forEach(b =>
    b.onclick = async () => {
      await api("/api/tests/" + b.dataset.open + "/open", {method: "POST"});
      toast("Test opened", "ok"); refresh(true); goto("serve");
    });
}

/* ------------------------------------------------------------------ setup */
function setupReadForm() {
  return {
    title: $("fTitle").value, subject: $("fSubject").value,
    num_questions: Math.max(2, Math.min(102, parseInt($("fQuestions").value || "20", 10))),
    options_per_question: S.opts, student_id_digits: S.digits,
    page_size: S.paper, answer_key: S.key,
    sheet_instructions: $("fInstructions").value,
    header_font_scale: parseFloat($("fHeaderScale").value) || 1.0,
    logo_position: S.logo || "left",
  };
}
function renderKeyGrid() {
  const n = Math.max(2, Math.min(102, parseInt($("fQuestions").value || "20", 10)));
  const letters = "ABCDE".slice(0, S.opts);
  const cols = n > 60 ? 4 : n > 24 ? 3 : n > 8 ? 2 : 1;
  const per = Math.ceil(n / cols);
  const grid = $("keyGrid");
  grid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
  let html = "";
  for (let c = 0; c < cols; c++) {
    html += `<div style="display:flex; flex-direction:column; gap:6px">`;
    for (let r = c * per; r < Math.min(n, (c + 1) * per); r++) {
      const q = r + 1, v = S.key[q];
      html += `<div class="kcell"><span class="qn">${q}</span>
        <button data-q="${q}" class="${v ? "set" : ""}">${v || "–"}</button></div>`;
    }
    html += `</div>`;
  }
  grid.innerHTML = html;
  grid.querySelectorAll("button").forEach(b => b.onclick = () => {
    const q = +b.dataset.q;
    const cur = S.key[q];
    if (!cur) S.key[q] = letters[0];
    else if (cur === letters[letters.length - 1]) delete S.key[q];
    else S.key[q] = letters[letters.indexOf(cur) + 1];
    renderKeyGrid();
  });
}
function initSetup() {
  ["fTitle", "fQuestions"].forEach(id => $(id).addEventListener("input", renderKeyGrid));
  const segs = [["fOptions", "opts", 4], ["fDigits", "digits", 7],
                ["fPaper", "paper", "a4"], ["fLogo", "logo", "left"]];
  segs.forEach(([id, prop, dflt]) => {
    $(id).querySelectorAll("button").forEach(b => b.onclick = () => {
      $(id).querySelectorAll("button").forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      const v = b.dataset.v;
      S[prop] = (prop === "paper") ? v : parseInt(v, 10);
      if (prop === "opts") {          // drop out-of-range key entries
        const letters = "ABCDE".slice(0, S.opts);
        Object.keys(S.key).forEach(q => { if (!letters.includes(S.key[q])) delete S.key[q]; });
      }
      renderKeyGrid();
    });
  });
  $("keyRandom").onclick = () => {
    const letters = "ABCDE".slice(0, S.opts);
    const n = Math.max(2, Math.min(102, parseInt($("fQuestions").value || "20", 10)));
    S.key = {}; for (let q = 1; q <= n; q++) S.key[q] = letters[Math.floor(Math.random() * letters.length)];
    renderKeyGrid();
  };
  $("keyClear").onclick = () => { S.key = {}; renderKeyGrid(); };
  $("keyLoad").onclick = () => {
    const txt = $("keyPaste").value.toUpperCase();
    const n = Math.max(2, Math.min(102, parseInt($("fQuestions").value || "20", 10)));
    const letters = "ABCDE".slice(0, S.opts);
    S.key = {};
    const kv = txt.match(/(\d{1,3})\s*[:.\-]\s*([A-E])/g);
    if (kv && kv.length >= 2) {
      kv.forEach(m => { const [, q, a] = m.match(/(\d{1,3})\s*[:.\-]\s*([A-E])/);
        if (+q <= n && letters.includes(a)) S.key[+q] = a; });
    } else {
      const compact = txt.replace(/[^A-E]/g, "");
      [...compact].slice(0, n).forEach((a, i) => { if (letters.includes(a)) S.key[i + 1] = a; });
    }
    renderKeyGrid();
    toast(Object.keys(S.key).length + " key entries loaded", "ok");
  };
  $("fHeaderScale").oninput = () =>
    $("fHeaderScaleVal").textContent = Math.round($("fHeaderScale").value * 100) + "%";
  $("createBtn").onclick = async () => {
    const body = setupReadForm();
    const err = $("setupErr"); err.style.display = "none";
    try {
      await api("/api/tests", {method: "POST",
        headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
      toast("Test created — sheet ready to print", "ok");
      (r.warnings || []).forEach(w => toast("ℹ " + w));
      $("previewBox").style.display = "";
      $("previewImg").src = "/api/preview.png?" + Date.now();
      refresh(true); goto("serve");
    } catch (e) {
      const errs = (e.data && e.data.errors) || ["Could not create the test."];
      err.textContent = "• " + errs.join("  • "); err.style.display = "";
    }
  };
}

/* ------------------------------------------------------------------ serve */
function renderServe() {
  const st = S.state; if (!st) return;
  updateServerPill(st);
  const sel = $("ipSel");
  const ips = st.server.ips || [];
  if (sel.dataset.ips !== ips.join()) {
    sel.dataset.ips = ips.join();
    sel.innerHTML = ips.map(i => `<option value="${esc(i)}">${esc(i)}</option>`).join("");
  }
  const ip = sel.value || ips[0];
  if (st.test) {
    $("srvUrl").value = `http://${ip}:${st.server.port}/scan/${st.test.session_token}`;
    $("qrImg").src = st.server.running
      ? "/api/qr.png?ip=" + encodeURIComponent(ip) + "&t=" + Date.now() : "";
    $("qrImg").style.display = st.server.running ? "" : "none";
  } else {
    $("srvUrl").value = "— create a test first —";
    $("qrImg").style.display = "none";
  }
}
function updateServerPill(st) {
  const p = $("srvPill"), b = $("srvBtn");
  if (st.server.running) {
    p.className = "pill ok"; p.textContent = "● server online :" + st.server.port;
    b.textContent = "■  Stop server"; b.className = "btn danger";
  } else {
    p.className = "pill off"; p.textContent = "● server offline";
    b.textContent = "▶  Start server"; b.className = "btn";
  }
}
function initServe() {
  $("srvBtn").onclick = async () => {
    const st = S.state;
    if (st && st.server.running) {
      await api("/api/serve/stop", {method: "POST"}); toast("Server stopped");
    } else {
      const r = await api("/api/serve/start", {method: "POST"});
      if (r.ok) toast("Server started — " + r.url, "ok");
      else toast("Could not start: " + (r.error || ""), "err");
    }
    refresh(true); renderServe();
  };
  $("copyBtn").onclick = () => {
    const v = $("srvUrl").value;
    if (v.startsWith("http")) { navigator.clipboard.writeText(v); toast("Link copied", "ok"); }
  };
  $("ipSel").onchange = () => renderServe();
  $("revealBtn").onclick = async e => { e.preventDefault(); await api("/api/reveal"); };
}

/* ----------------------------------------------------------------- review */
async function loadReview() {
  S.reviewItems = await api("/api/review");
  $("reviewCount").textContent = S.reviewItems.length;
  const list = $("reviewList");
  list.innerHTML = S.reviewItems.length ? "" :
    '<p class="muted" style="font-size:13px">Nothing flagged — clean sailing ✨</p>';
  S.reviewItems.forEach(it => {
    const el = document.createElement("div");
    el.className = "ritem" + (S.reviewSel === it.sheet_id ? " active" : "");
    el.innerHTML = `<b>⚑ ${esc(it.student_id || "no ID")}</b>
      <div class="m">${it.flags.length} flag(s) · ${it.score}/${it.max_score} ·
      ${esc((it.ts || "").slice(11))}</div>`;
    el.onclick = () => { S.reviewSel = it.sheet_id; loadReview(); };
    list.appendChild(el);
  });
  const item = S.reviewItems.find(x => x.sheet_id === S.reviewSel) || S.reviewItems[0];
  const box = $("reviewDetail");
  if (!item) {
    box.innerHTML = `<h3>Nothing flagged — clean sailing ✨</h3>
      <p class="sub">Ambiguous sheets will appear here automatically.</p>`;
    return;
  }
  S.reviewSel = item.sheet_id;
  S.overrides = {};
  const st = S.state, letters = "ABCDE".slice(0,
    st && st.test ? st.test.options_per_question : 4);
  box.innerHTML = `
    <h3>⚑ Sheet <span class="mono">${esc(item.student_id || "?")}</span>
      <span class="badge warn">${item.flags.length} to verify</span></h3>
    <p class="sub">Pick the intended answer for each disputed item, then export.
       “Blank” records no answer (marked wrong).<br>
       Keyboard: <b>←/→</b> move · <b>1–5</b> pick option · <b>B</b> blank ·
       <b>Enter</b> confirm.</p>
    <div class="idrow"><span style="font-weight:700; font-size:13px">Student ID</span>
      <input type="text" id="revId" maxlength="10" value="${esc(item.student_id || "")}"></div>
    <div id="flagsBox"></div>
    <div style="display:flex; gap:10px; margin-top:14px">
      <button class="btn ok" id="revConfirm" style="flex:1">✔  Confirm &amp; export</button>
      <button class="btn danger" id="revDiscard">🗑 Discard</button>
    </div>`;
  const flagsBox = $("flagsBox");
  S.flagIdx = 0;
  item.flags.forEach((f, i) => {
    S.overrides[i] = f.guess ?? null;
    const card = document.createElement("div");
    card.className = "flagcard";
    card.dataset.flag = i;
    card.tabIndex = -1;
    card.innerHTML = `
      ${f.crop ? `<img src="${esc(f.crop)}" alt="crop">` :
        `<div class="muted" style="font-size:12px">no preview</div>`}
      <div>
        <b style="color:var(--warn2); font-size:13.5px">${esc(kindLabel(f.kind))}</b>
        <div class="muted" style="font-size:12.5px; margin:3px 0">${esc(f.message)}</div>
        <div class="ops">${letters.split("").map(L =>
          `<button data-v="${L}" class="${f.guess === L ? "set" : ""}">${L}</button>`).join("")}
          <button data-v="" class="${!f.guess ? "set" : ""}" style="min-width:64px">Blank</button>
        </div>
      </div>`;
    card.querySelectorAll(".ops button").forEach(b => b.onclick = () => {
      S.overrides[i] = b.dataset.v || null;
      card.querySelectorAll(".ops button").forEach(x => x.classList.remove("set"));
      b.classList.add("set");
    });
    flagsBox.appendChild(card);
  });
  const paintSel = () => box.querySelectorAll(".flagcard").forEach((el, i) =>
    el.style.opacity = i === S.flagIdx ? "1" : ".55");
  paintSel();
  box.onkeydown = e => {
    const letters = "ABCDE".slice(0,
      st && st.test ? st.test.options_per_question : 4);
    const cards = box.querySelectorAll(".flagcard");
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      S.flagIdx = (S.flagIdx + (e.key === "ArrowRight" ? 1 : cards.length - 1))
                  % cards.length;
      paintSel(); e.preventDefault();
    } else if (/^[1-5]$/.test(e.key) && +e.key <= letters.length) {
      const b = cards[S.flagIdx].querySelector(
        `.ops button[data-v="${letters[+e.key - 1]}"]`);
      if (b) b.click();
    } else if (e.key.toLowerCase() === "b") {
      cards[S.flagIdx].querySelector('.ops button[data-v=""]').click();
    } else if (e.key === "Enter") {
      $("revConfirm").click();
    }
  };
  box.tabIndex = 0;
  $("revConfirm").onclick = async () => {
    const answers = {};
    item.flags.forEach((f, i) => { if (f.q != null) answers[f.q] = S.overrides[i]; });
    try {
      await api("/api/review/resolve", {method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({sheet_id: item.sheet_id, answers,
                              student_id: $("revId").value})});
      toast("Resolved & exported to CSV", "ok");
      S.reviewSel = null; refresh(true); loadReview();
    } catch { toast("Could not resolve", "err"); }
  };
  $("revDiscard").onclick = async () => {
    await api("/api/review/discard", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({sheet_id: item.sheet_id})});
    toast("Sheet discarded"); S.reviewSel = null; refresh(true); loadReview();
  };
}
const kindLabel = k => ({BLANK: "Unanswered", MULTI: "Double mark",
  FAINT: "Faint mark", ID: "Student ID"}[k] || k);

/* ---------------------------------------------------------------- results */
async function loadResults() {
  S.rows = await api("/api/results");
  renderResults();
}
function renderResults() {
  const q = ($("resFilter").value || "").trim();
  const rows = S.rows || [];
  const shown = q ? rows.filter(r => (r.Student_ID || "").includes(q)) : rows;
  const body = $("resBody");
  if (!shown.length) {
    body.innerHTML = `<tr><td colspan="7" class="muted" style="padding:22px">
      ${rows.length ? "No match." : "No graded sheets yet."}</td></tr>`;
    $("resStat").textContent = "—"; $("resHisto").innerHTML = ""; return;
  }
  const scores = shown.map(r => +r.Total_Score || 0);
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
  $("resStat").textContent =
    `${shown.length} sheets · avg ${(avg).toFixed(1)} · high ${Math.max(...scores)} · low ${Math.min(...scores)}`;
  renderHisto(scores, shown[0] ? +shown[0].Max_Score || 0 : 0);
  body.innerHTML = shown.slice().reverse().map((r, i) => `<tr>
    <td class="muted">${i + 1}</td>
    <td class="mono">${esc((r.Timestamp || "").slice(11, 19))}</td>
    <td><b>${esc(r.Student_ID || "—")}</b></td>
    <td><b>${r.Total_Score}</b><span class="muted">/${r.Max_Score}</span></td>
    <td>${r.Percent ?? "—"}</td>
    <td>${r.confidence != null ? `<div class="confbar"><i style="width:${Math.round(r.confidence * 100)}%"></i></div>` : "—"}</td>
    <td>${r.Status === "Verified" ? '<span class="badge ok">✔ verified</span>' :
        '<span class="badge warn">⚑ flagged</span>'}</td>
  </tr>`).join("");
}

function renderHisto(scores, max) {
  const nb = 10;                                  // decile buckets
  const buckets = new Array(nb).fill(0);
  scores.forEach(s => {
    const b = Math.min(nb - 1, max ? Math.floor(s / max * nb) : 0);
    buckets[b]++;
  });
  const top = Math.max(...buckets, 1);
  $("resHisto").innerHTML =
    `<div style="display:flex; align-items:flex-end; gap:2px; height:46px; margin-bottom:2px">` +
    buckets.map((n, i) =>
      `<div title="${Math.round(i * max / nb)}–${Math.round((i + 1) * max / nb)} pts: ${n}"` +
      ` style="flex:1; height:${Math.round(n / top * 100)}%; min-height:2px;` +
      ` background:${i >= 8 ? "var(--ok)" : i >= 5 ? "var(--brand)" : "var(--bg3)"}"` +
      `></div>`).join("") +
    `</div><div class="muted" style="font-size:10px; letter-spacing:.08em">SCORE DISTRIBUTION</div>`;
}

/* --------------------------------------------------------------- settings */
const SETTING_DEFS = {
  engine: [
    ["t_fill", "Bubble fill threshold", 0.05, 0.8, 0.01, null,
     "Dark-pixel ratio above which a bubble counts as filled."],
    ["t_blank", "Blank threshold", 0.02, 0.4, 0.01, null,
     "Below this the bubble is treated as untouched."],
    ["faint_upper", "Faint-mark ceiling", 0.2, 0.95, 0.01, null,
     "A fill between the fill threshold and this value is flagged as faint."],
    ["multi_ratio", "Double-mark ratio", 0.3, 0.95, 0.01, null,
     "If the 2nd-darkest bubble exceeds top × this ratio → flagged."],
    ["dark_threshold_offset", "Binarisation offset", -60, 60, 1, null,
     "Shifts the auto black/white cut-off. Raise for light pencils."],
    ["warp_width_px", "Flatten width (px)", 1000, 2400, 20, null,
     "Resolution of the perspective-corrected page."],
    ["auto_accept_blank", "Auto-accept blank answers", null, null, null, true,
     "Blank = wrong, without appearing in the review queue."],
    ["save_debug_warp", "Save flattened page images", null, null, null, true,
     "Keep a top-down PNG of every graded sheet (debug / audit)."],
  ],
  camera: [
    ["jpeg_quality", "JPEG quality", 60, 100, 1, null,
     "Quality of photos sent from the phone."],
    ["target_width_px", "Capture width target (px)", 1280, 4096, 64, null,
     "Requested camera resolution on the phone."],
  ],
  server: [
    ["port", "Port", 1024, 65535, 1, null, "Restart the server after changing."],
    ["host", "Bind address", null, null, null, false,
     "0.0.0.0 = all interfaces (LAN reachable)."],
    ["max_upload_mb", "Max upload (MB)", 5, 100, 1, null, ""],
    ["master_csv", "Also append to master_results.csv", null, null, null, true,
     "One combined CSV across all tests."],
  ],
};

async function loadSettings() {
  const s = await api("/api/settings");
  ["engine", "camera", "server"].forEach(group => {
    const host = $("set" + group[0].toUpperCase() + group.slice(1));
    host.innerHTML = SETTING_DEFS[group].map(([key, lab, lo, hi, step, isSw, desc]) => {
      const val = s[key];
      if (isSw) return `<div class="setting">
        <div><div class="lab">${lab}</div><div class="desc">${desc}</div></div>
        <div class="switch ${val ? "on" : ""}" data-key="${key}"></div></div>`;
      if (lo === null) return `<div class="setting">
        <div><div class="lab">${lab}</div><div class="desc">${desc}</div></div>
        <input type="text" data-key="${key}" value="${esc(val)}" style="max-width:190px"></div>`;
      return `<div class="setting">
        <div class="lab">${lab}<span class="val" id="v_${key}">${fmt(val)}</span></div>
        <div><input type="range" data-key="${key}" min="${lo}" max="${hi}"
          step="${step}" value="${val}"></div>
        <div class="desc">${desc}</div></div>`;
    }).join("");
  });
  $("setDataDir").textContent = "Data folder: " + (S.state ? S.state.data_dir : "");
  document.querySelectorAll("#page-settings .switch").forEach(sw => sw.onclick = () => {
    sw.classList.toggle("on");
    saveOne(sw.dataset.key, sw.classList.contains("on"));
  });
  document.querySelectorAll("#page-settings input[type=range]").forEach(sl => {
    sl.oninput = () => { $("v_" + sl.dataset.key).textContent = fmt(sl.value); };
    sl.onchange = () => saveOne(sl.dataset.key, +sl.value);
  });
  document.querySelectorAll("#page-settings input[type=text]").forEach(inp =>
    inp.onchange = () => saveOne(inp.dataset.key, inp.value));
}
const fmt = v => (+v % 1 === 0) ? String(+v) : (+v).toFixed(2);
async function saveOne(key, value) {
  await api("/api/settings", {method: "POST",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify({[key]: value})});
}

/* ------------------------------------------------------------------- faq */
function renderFaq() {
  $("faqList").innerHTML = FAQ.map(([q, a], i) =>
    `<details class="faq"${i === 0 ? " open" : ""}><summary>${esc(q)}</summary>
     <p>${esc(a)}</p></details>`).join("");
}

/* ----------------------------------------------------------------- log */
function renderLog(st) {
  const box = $("logBox");
  const log = st.log || [];
  if (!log.length) return;
  box.innerHTML = log.map(ev => {
    const t = new Date((ev.ts || 0) * 1000).toTimeString().slice(0, 8);
    let cls = "in", txt = "";
    switch (ev.type) {
      case "log": txt = ev.message; break;
      case "sheet_graded": cls = "ok";
        txt = `✔ ${ev.result.student_id || "(no ID)"} graded — ${ev.result.score}/${ev.result.max_score} · ${ev.result.duration_ms} ms`; break;
      case "sheet_flagged": cls = "fl";
        txt = `⚑ ${ev.result.student_id || "(no ID)"} flagged (${ev.result.flags.length} item${ev.result.flags.length > 1 ? "s" : ""}) → review queue`; break;
      case "sheet_rejected": cls = "er";
        txt = `✕ rejected [${ev.code}] ${ev.message}`; break;
      case "review_resolved": cls = "ok";
        txt = `✔ review resolved — ${ev.student_id || "?"} ${ev.score} pts → CSV`; break;
      case "server_started": cls = "ok"; txt = "● server started — " + (ev.url || ""); break;
      case "server_stopped": txt = "○ server stopped"; break;
      default: return "";
    }
    return `<div><span class="t">${t}</span><span class="${cls}">${esc(txt)}</span></div>`;
  }).join("");
  box.scrollTop = box.scrollHeight;
}

/* -------------------------------------------------------------- polling */
let refreshing = false;
async function refresh(force = false) {
  if (refreshing) return; refreshing = true;
  try {
    const st = await api("/api/state");
    const logGrew = (st.log || []).length !== S.lastLogLen;
    S.state = st; S.lastLogLen = (st.log || []).length;
    $("ver").textContent = st.version;
    document.querySelectorAll(".ver").forEach(e => e.textContent = st.version);
    $("dataDir").textContent = st.data_dir;
    updateServerPill(st);
    if (S.page === "dashboard") renderDashboard();
  api("/api/tests").then(tl => { S.tests = tl;
    if (S.page === "dashboard") renderDashboard(); }).catch(() => {});
    if (S.page === "serve") { renderServe(); if (logGrew || force) renderLog(st); }
    if (S.page === "review") {
      $("navReviewBadge").textContent = st.stats.pending_review;
      $("navReviewBadge").classList.toggle("show", st.stats.pending_review > 0);
      const tb = $("tabReviewBadge");
      if (tb) { tb.textContent = st.stats.pending_review;
        tb.classList.toggle("show", st.stats.pending_review > 0); }
      if (st.stats.pending_review !== S.reviewItems.length && !S.reviewSel) loadReview();
    }
    if (S.page === "results" && st.stats.exported !== (S.state && 0)) { /* poll below */ }
  } catch (e) { /* server restarting */ }
  refreshing = false;
}

/* ----------------------------------------------------------------- init */
function init() {
  buildTabs();
  document.querySelectorAll(".nav a.item").forEach(a => a.onclick = () => goto(a.dataset.page));
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => goto(t.dataset.page));
  document.querySelectorAll("[data-goto]").forEach(el =>
    el.onclick = () => goto(el.dataset.goto));
  initSetup(); initServe();
  $("resFilter").oninput = () => renderResults();
  $("themeBtn").onclick = () => {
    const cur = document.documentElement.dataset.theme || "dark";
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("ob_theme", next);
    $("brandLogo").src = next === "dark" ? "/assets/logo-wordmark-white.png"
                                        : "/assets/logo-wordmark-navy.png";
  };
  const saved = localStorage.getItem("ob_theme");
  if (saved === "light") $("themeBtn").click();
  goto("dashboard");
  refresh(true);
  setInterval(() => { if (!document.hidden) refresh(); }, 2000);
  setInterval(() => { if (!document.hidden && S.page === "results") loadResults(); }, 4000);
}
document.addEventListener("DOMContentLoaded", init);
