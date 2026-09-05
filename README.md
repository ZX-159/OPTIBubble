<div align="center">

<img src="docs/hero.png" alt="OPTIBubble" width="860"/>

**Local computer-vision OMR grading with a zero-install mobile scanner.**

Print dynamic answer sheets → users photograph them with **any phone browser** over Wi-Fi → OpenCV grades them on **your** computer → ambiguous marks land in a review queue → export to CSV.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Tauri 2](https://img.shields.io/badge/native%20shell-Tauri%202-FFC131?logo=tauri&logoColor=white)](#-native-app-tauri-optional)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-425466)](#-platform-support)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-22C55E.svg)](LICENSE)
[![Privacy](https://img.shields.io/badge/privacy-100%25%20local%2C%20no%20cloud-3B82F6)](#-privacy)
[![Self-test](https://img.shields.io/badge/self--test-green-22C55E)](#-development)

*No Scantron hardware. No cloud subscription. No app store. Every scan, grade and export stays on your own machine.*

**Wordmark set in OPTIBubble · UI set in Instrument Sans · micro-labels in IBM Plex Mono · accents in Instrument Serif** — all bundled offline. Light **and** dark mode, toggle system-wide.

</div>

---

## 🎨 Design language — *LEDGER*

The interface is built on **LEDGER** — a light-first, instrument-grade UI with
a warm paper content plane, plus a full **dark mode** (`theme-ink`) toggled
system-wide from the top-right moon/sun control and persisted across sessions.
It is named after what the product does: putting a camera, four corner anchors
and a printed sheet on one line of sight — and the marks that become the record.

| Token | Light | Dark | Role |
|---|---|---|---|
| Desk / card | `#F6F7F9 / #FFF` | `#0B0E13 / #10141A` | the chrome ladder — silent, hairline-separated |
| Text / secondary / tertiary | `#1B2430 / #4A5563 / #6C7686` | `#EEF1F5 / #A9B2BE / #6E7886` | text ladder |
| Paper | `#FBF7EE` | `#F7F2E7` | the printed sheet — always the warmest object on screen |
| Iris (brand) | `#2F6FED` | `#6A8DF6` | **the machine**: selection, active state, primary action, data |
| Vermilion | `#E5484D` | `#F06B7E` | **the grading pen**: appears only where a human or the engine intervened — flags, evidence rings |
| Verdicts | mint / amber / rose | same family (lightened) | confident · ambiguous · double-marked (semantic only, never branding) |

Rules of the system: **nothing floats** — surfaces are separated by 1px
hairlines and a half-step of lightness, shadows are reserved for the paper
artifact itself; micro-labels are IBM Plex Mono uppercase tracked out like
instrument silkscreen; every comparable number uses tabular figures; the
*registration-mark* crosshair precedes section labels, *corner brackets* frame
the viewfinder, sheet and evidence crops, and the *pen ring* marks any bubble
a human has to look at. Every control carries the full interactive-state
matrix (idle · hover · focus-visible · active · disabled · loading · success ·
error). Motion is real spring physics (staggered entrances, shared-layout
transitions) that **honours `prefers-reduced-motion`**. Fonts are bundled
locally — fully offline.

Grown from the reference patterns at **KokonutUI**, **Watermelon UI** and
**Motion.dev**: the home screen is a **dedicated Dashboard** — a KPI card grid
(big animated numeral · icon · delta · mini sparkline), a score-distribution
histogram, a live KR-20 reliability + hardest-questions panel, a recent-activity
feed and a state-aware *next step* card, plus **⌘K / Ctrl-K** quick-jump to any
screen and a collapsible sidebar.

On paper, the sheet brand colour is **#2e5a99** (white on dark backgrounds),
applied to the embedded wordmark and the header rule.

---

## ✨ Features

| | |
|---|---|
| 🖨 **Dynamic sheet generator** | 2–102 questions, 2–5 options (A–B … A–E), auto multi-column layout, up to 10-digit student-ID grid, session QR code, four machine-vision alignment anchors. A4 & US Letter. |
| 📷 **USB document camera station** | Plug any USB doc cam / webcam into the PC and grade without phones — live preview on Scan & Serve plus one-click *Capture & grade* through the same pipeline. |
| ⚖️ **Weighted scoring & partial credit** | Per-question points (e.g. `5:2, 9-12:3`) and an automatic partial-credit fraction for double-marks that still contain the key. |
| 📈 **Psychometric analytics** | Per test: item error rates, discrimination (point-biserial) and **KR-20 reliability**, rendered live on the Dashboard and Results pages as a **radial KR-20 gauge**, a **score-distribution histogram** with a mean line, and **toughest-question bars** with discrimination dots — all as dependency-free, theme-aware inline SVG (fast, no chart library). |
| 🔐 **Archiving: export & import** | One button packages a whole test — sheet, key, photos, crops, results — into a `.optibubble` file for flash drives, **with an optional password** (AES-256 when set, plain when not); the matching **Import** button restores it on any machine. |
| 📡 **Phone mirror (WebRTC)** | The phone's live viewfinder streams to the desktop over the LAN — check framing at a glance while the phone stays the hand scanner. |
| 🎯 **Live anchor-lock overlay** | The phone viewfinder finds the four printed black squares in real time (on-device flood-fill + square filters, ~4 ms/frame) and locks corner brackets onto them; when a corner is hidden it falls back to a Sobel-edge framing quad. An *aligned — hold steady* state plus optional **auto-capture** when the sheet is stable. |
| 🔢 **Digit-aware student-ID review** | Flagged ID rows offer 0–9 (not A–D!); picking a digit writes it straight into the ID field, and the keyboard follows the same rule. |
| 🔎 **Result detail view** | Click any graded row for a per-question breakdown — score tiles plus colour-coded answer chips from the stored JSON. |
| 📊 **System info & in-app self-test** | Settings → System shows version, Python/OpenCV/platform, storage used, network + HTTPS status and lifetime counters — plus a button that runs the full self-test suite and prints the verdict in-app. |
| ⚛️ **React + Tailwind + Motion front-end** | The desktop app and phone scanner are a single React SPA (Vite build served by the engine — still zero-internet) with a complete interactive-state system: loading, error, success, idle, hover, focus-visible, active and disabled states on every control. |
| 🔑 **Answer key printing** | A one-page answer-key PDF — grid of Q#→letter plus a compact string — generated with every test and **auto-refreshed when the key changes**. One button next to the sheet PDF on Scan & Serve. |
| ✏️ **Sheet designer** | Editable title, custom instructions, header text size (80–140 %), wordmark side and **handwritten write-in fields** (Name/Class/Date…, ignored by the scanner) — all inside the header, with **auto-shrink instead of overlap** and a header layout that is *proven* collision-free before the PDF is written. The OPTIBubble wordmark prints in **#2e5a99** (white on dark media). |
| 🗂 **Test management** | Every test keeps its own sheets, review queue and CSV. Open, **edit** (title/subject/key/design — the sheet PDF regenerates), **delete** with confirmation, and see which test is *active* via context chips on Serve/Review/Results. |
| 🎲 **Auto answer key** | Leave the key empty and a complete key is generated automatically — create a test in seconds, edit the key any time, even after sheets are printed. |
| 🔍 **Evidence cards & lightbox** | Every flagged item shows a framed, legible evidence crop (scrollable for wide strips); click to inspect full-screen, Esc to close. |
| 🔑 **Print-first workflow** | Create and print sheets with a partial (or empty) answer key; finish the key later on the Scan & Serve page — grading scores whatever is already defined. |
| 📱 **Mobile web bridge + HTTPS** | A QR link opens a premium scanner page — live viewfinder, torch, quality check, instant feedback. Two HTTPS modes: **Trusted (zero user setup)** — built-in Let's Encrypt client issues a publicly-trusted cert for your free `*.duckdns.org` domain via DNS-01, so the camera just works in any browser; or **Local CA (fully offline)** — users scan code A once. iOS & Android. |
| 🔍 **Real OMR pipeline** | **Three-pass anchor detection** (sharp Otsu → adaptive threshold + morphological close for glare/shadow → relaxed filters for folded corners) → perspective warp → grid-relative per-bubble dark-pixel-density analysis with a confidence model. A typical photo grades in **~80 ms** on a laptop CPU; long sessions are bounded (capped receipts, cached CSV reads, no leaked queues). |
| ⚑ **Confidence flagging** | Unanswered, double-marked and faint/partially-erased marks are flagged and shown as zoomable crops — one click to override and export. |
| 🖥 **Modern desktop UI** | A premium web app served by the engine itself — a **dedicated Dashboard home** (large KPI cards with real sparklines + context, radial KR-20 gauge, score histogram, toughest-question bars, recent activity, a state-aware *next step*), **dark mode** system-wide, **⌘K / Ctrl-K** quick-jump, and dashboard → review → export — wrapped in a native window by the bundled **Tauri 2** shell, or just run it in your browser. |
| 📊 **Live CSV export & analytics** | Every verified sheet appends instantly to `results.csv` (+ optional master CSV). Results view adds a score-distribution histogram, ID filtering, and duplicate-submission warnings. |
| ⌨️ **Keyboard review** | Fly through flagged sheets: ←/→ move between items, 1–5 pick an option, B blank, Enter confirm. |
| ⚙️ **Advanced fine-tuning + built-in guide** | Every engine threshold — fill, blank, ambiguity band, double-mark ratio, binarisation offset, warp resolution — live in Settings, each with a plain-English hint, **one-tap presets** (ballpoint / pencil / low light / soft pencil), and a **“How bubble checking works”** panel explaining BLANK / FAINT / MULTI and exactly when a mark is auto-accepted vs. sent for review. |
| 🔌 **Offline-first** | Desktop app, mobile page, fonts, everything is served from your machine over the LAN. Zero internet required after install. |

---

## 🏗 How it works

```
┌────────────────────────────  YOUR COMPUTER  ────────────────────────────┐
│                                                                          │
│  Desktop UI (web app — browser or the Tauri native shell)               │
│   ├── Test setup + answer key ──► printable sheet.pdf (ReportLab)       │
│   │                                    │                                │
│   └── Embedded Flask server ◄───────────┘   magic link + QR             │
│        │   http://192.168.x.x:5000/scan/<session>                       │
└────────┼─────────────────────────────────────────────────────────────────┘
         │  local Wi-Fi (phones & PC on the same router)
   ┌─────┴─────┐  ┌───────────┐  ┌───────────┐
   │ 📱 phone 1 │  │ 📱 phone 2 │  │ 📱 phone n │   ← native browser only
   └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
         │  JPEG photo POST             │
         ▼                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  OpenCV engine — anchors → warp → bubble density → confidence scoring   │
│   ├── high confidence ─────────────────────────► auto-grade → CSV       │
│   └── blank / double / faint ──► Review Queue (crops + overrides) ──► CSV│
└──────────────────────────────────────────────────────────────────────────┘
```

![Pipeline](docs/pipeline.jpg)
*A real run: anchor detection → perspective correction → per-bubble classification (green = confident · grey = blank · amber = faint · red = double-mark).*

---

## 📸 Screens

The app opens straight to the **Dashboard**. The whole UI comes in two themes —
**light** and **dark** (toggle top-right, persisted across sessions).

| Dashboard — home (light) | Dashboard — home (dark) |
|---|---|
| ![Dashboard](docs/screenshots/01-dashboard.png) | ![Dashboard dark](docs/screenshots/01-dashboard-dark.png) |

| New test & answer key | Scan & Serve — magic link |
|---|---|
| ![Setup](docs/screenshots/03-setup.png) | ![Session](docs/screenshots/02-session.png) |

| Test library | Review queue with evidence crops |
|---|---|
| ![Tests](docs/screenshots/04-tests.png) | ![Review](docs/screenshots/05-review.png) |

| Results & CSV export | Settings (every threshold live, with hints + presets + bubble-checking guide) |
|---|---|
| ![Results](docs/screenshots/06-results.png) | ![Settings + OMR guide](docs/screenshots/07-settings-omr.png) |

| Help & FAQ | Mobile scanner (phone browser) |
|---|---|
| ![Help](docs/screenshots/08-help.png) | ![Mobile](docs/screenshots/09-mobile-scanner.png) |

| Mobile scanner — camera view (torch, rear/front switch, mirror, quality telemetry) |
|---|
| ![Mobile camera](docs/screenshots/09-mobile-scanner-camera.png) |

**Dark mode everywhere** — every screen (and the phone scanner) carries a matching
`theme-ink` variant; captures below are dark equivalents of the screens above:

| Dashboard (dark) | Session (dark) |
|---|---|
| ![Dashboard dark](docs/screenshots/01-dashboard-dark.png) | ![Session dark](docs/screenshots/02-session-dark.png) |

| Review (dark) | Results (dark) |
|---|---|
| ![Review dark](docs/screenshots/05-review-dark.png) | ![Results dark](docs/screenshots/06-results-dark.png) |

<details>
<summary><b>More — dark variants & generated sheet / simulated phone photo</b></summary>

| Settings (dark) | Help & FAQ (dark) |
|---|---|
| ![Settings dark](docs/screenshots/07-settings-dark.png) | ![Help dark](docs/screenshots/08-help-dark.png) |

The phone scanner shares the same engine & fonts and auto-respects the system
dark-mode preference (toggle + persist):

| Mobile scanner (light) | Mobile scanner (dark) |
|---|---|
| ![Mobile](docs/screenshots/09-mobile-scanner.png) | ![Mobile dark](docs/screenshots/09-mobile-scanner-dark.png) |

A generated **100-question / 5-option** sheet, and a *simulated* phone photo of a filled sheet
(perspective + shadows + noise + JPEG) used by the self-test:

| 100-question sheet | Simulated phone photo |
|---|---|
| ![Sheet](docs/sheet-sample.png) | ![Photo](docs/photo-sample.jpg) |

</details>

A generated **100-question / 5-option** sheet, and a *simulated* phone photo of a filled sheet
(perspective + shadows + noise + JPEG) used by the self-test:

| 100-question sheet | Simulated phone photo |
|---|---|
| ![Sheet](docs/sheet-sample.png) | ![Photo](docs/photo-sample.jpg) |

</details>

---

## 🚀 Quick start (Python — any platform)

> Building installers, uploading to GitHub or cutting releases? Jump straight to
> **[`setup.md`](setup.md)** — the full build & release guide (Windows, macOS,
> Linux AppImage/deb/RPM and Flatpak via GitHub Actions).

### 1 · Install

```bash
git clone https://github.com/<you>/OPTIBubble.git
cd OPTIBubble

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

> Python 3.9+ · Windows 10/11, macOS 12+, Linux.

### 1b · Build the web UI (Node is required once, to build the React SPA)

```bash
cd frontend
npm install
npm run build        # writes optibubble/web/dist — served by the engine
cd ..
```

The desktop app and phone scanner are a single React SPA served by the engine itself.
It must be built before the first run (a fresh clone ships no `dist/`); without it the
app comes up in its legacy HTML fallback. End users of a **packaged installer** never
need Node — the built SPA is bundled with the frozen engine.

### 2 · Run the self-test (recommended)

```bash
python selftest.py
```

Builds a sheet, simulates filled bubbles (pen strokes, partial marks), synthesises phone
photos (perspective jitter, brightness gradients, sensor noise, JPEG artefacts) across
random seeds, and asserts exact scores, flag types, student-ID reads, the full HTTP
stack, the HTTPS bridge, archive round-trips and the < 3 s latency budget — expect
**all green** (85 checks).

### 3 · Launch

```bash
python main.py          # opens the desktop app in your browser
```

### 4 · Run your first test (3 minutes)

The app opens on the **Dashboard**, which shows a *next step* card that guides you
along the flow — Create → Collect → Grade.

1. **Create a test** — hit **New test** on the Dashboard (or `⌘K` → *New test*) and set
   title, questions, options; click through the answer-key cells (or paste `1:A 2:C …`
   / `ACBD…`, or randomise). **Create test & generate sheet.** The Dashboard then shows
   the test as *active* and the QR magic-link as the next step.
2. **Scan & Serve** — open the sheet PDF and print at **100 % (“Actual size”)**.
   Hand out the sheets. Press **Start server** — the QR magic link appears; students
   open it and scan filled sheets.
3. Users scan it with the phone's regular camera; the scanner opens in the browser.
   They photograph the sheet with all four corner squares inside the frame.
4. Results stream in live. Confident sheets are graded and exported instantly;
   anything ambiguous lands in **Review Queue** with a cropped image of the disputed
   bubble — pick the right option (or *Blank*), hit **Confirm & export**.
5. **Results** — the Dashboard now shows the graded count, mean score, a score
   distribution, and **KR-20** reliability with the hardest questions; export the CSV
   copy. Done. ☕

> **Networking tip:** phones and the computer must share a Wi-Fi network (a laptop
> hotspot works great). Allow Python through your firewall when prompted — that's
> the only network permission you'll ever need.

### CLI

```bash
python main.py --demo            # create a ready-to-play demo test
python main.py --serve T123456   # reopen a saved test & serve headless
python main.py --pdf T123456     # regenerate a sheet PDF
python main.py --port 5050       # run on another port
python main.py --selftest        # end-to-end verification
```

---

## ⬇️ Download & install (end users)

The one place to get a ready-to-run build is **the release page** (each release
carries a per-OS installer and a checksum file). How the channels are laid out —
the same pattern used by most major open-source desktop apps:

| Platform | What you download | Install it |
|---|---|---|
| **Windows** | `OPTIBubble_x.y.z_x64-setup.exe` (NSIS) or `.msi` | double-click the installer |
| **macOS (Apple Silicon)** | `OPTIBubble_x.y.z_aarch64.dmg` | open the dmg, drag to *Applications* |
| **macOS (Intel)** | `OPTIBubble_x.y.z_x64.dmg` | same |
| **Linux** | `OPTIBubble_x.y.z_amd64.AppImage` (portable — just run it) | `chmod +x …AppImage && ./…AppImage` |
| **Linux** | `…_.deb` / `…_.rpm` | `sudo dpkg -i …deb` / `sudo rpm -i …rpm` |
| **Linux (sandboxed)** | `OPTIBubble_…_x86_64.flatpak` | `flatpak install …flatpak` |

Every release is **self-contained** — the Python engine is frozen into a single
binary and bundled, so end users need nothing pre-installed (no Python, no pip).
Installers are published as a **draft release**; the maintainer reviews and
publishes it, so the list only ever shows verified builds.

**Verify what you download (supply-chain hygiene).** Every release also attaches
a `SHA256SUMS` file. To check an installer:

```bash
sha256sum -c SHA256SUMS     # Linux/macOS  (or: certutil -hashfile … SHA256 on Windows)
```

This is the same pattern the Linux ecosystem expects (a checksums file next to
the binaries), matching how large projects ship artifacts. Optional hardening:
the maintainer can add a **detached GPG signature** (`SHA256SUMS.asc`) and
**signature-verified publishing** later by dropping a GPG key into
`.github/workflows` — see [credits & licences](#-credits--licences).

> **First-run OS warnings.** The release pipeline can sign Windows binaries with
> an **Authenticode** certificate and **notarise** macOS DMGs once those
> credentials are configured (see [`setup.md`](setup.md)). Until then, Windows
> *SmartScreen* and macOS *Gatekeeper* may warn — click **More info → Run anyway**
> (Windows) or **right-click → Open** (macOS, once), on the first launch only.
> Linux builds carry **no warning at all**.

**Package managers (optional).** The same installers can be wired into per-OS
stores by maintainers or community members — Homebrew (macOS), `winget`/Scoop
(Windows), and Flathub (Linux) are the common upstream targets. The Flatpak
bundle is already built by CI, so publishing to **Flathub** only needs a
repository request ([✨ Features](#-features) & [setup.md](setup.md)).

---

## 🖥 Native app & installers (optional)

Prefer a real desktop window with its own icon, taskbar entry and installers?
The repo ships a **Tauri 2** shell in `src-tauri/` that wraps the exact same UI,
One GitHub Actions workflow (`.github/workflows/main.yml`) **freezes the Python
engine into a self-contained binary with PyInstaller** and produces fully
self-contained installers on every `v*` tag — **Windows MSI/NSIS, macOS dmg
(Intel + Apple Silicon), Linux AppImage, deb, RPM and a Flatpak**. End users
install and run — no Python, no pip, no setup:

```bash
cargo install tauri-cli --version "^2"
cargo tauri dev      # native window in dev mode (spawns the Python engine)
cargo tauri build    # installers → src-tauri/target/release/bundle/
```

The shell detects whether the engine is already running, spawns
`python main.py --no-browser` if not (passing a `--port-file` so it always
learns the port the engine actually bound — even when it had to fall back from
5000), waits for it, opens the native window at that port, and shuts the engine
down on exit.

➡ **Full instructions — local builds, GitHub upload, Actions release matrix,
Flatpak/RPM recipes — live in [`setup.md`](setup.md).**

---

## 📠 The mobile scanner

Served entirely from your PC — the page and its fonts are bundled, so it
works with **zero internet access**.

* Live viewfinder with a corner-bracket alignment overlay and guidance hints —
  **glare/shadow-adaptive anchor thresholds** and a **shape-validity gate** so the
  brackets stay sticky and never snap onto a wrong corner
* **Torch button** (true camera LED where exposed) and a **rear/front camera switch**
* Automatic (optional) capture once the sheet is aligned *and* steady
* **Client-side quick check** before upload: exposure, blur and corner-marker presence
* **Distinct, actionable states** — camera permission denied, no camera, camera in use,
  upload/network failure, OMR reject (with the reason), review (human check), and
  graded — each with its own message and retry/photo-fallback option
* Instant feedback: animated score card, or a friendly *“sent for review”*
* Falls back to the phone's **native camera app** (capture/upload) where the browser
  blocks the in-page camera — common on plain-HTTP LAN addresses — so scanning works
  on *any* device

---

## 🔒 Trusted HTTPS — the live camera with zero per-user setup

**The problem.** Mobile browsers only allow the in-page camera
(`getUserMedia`) inside a *secure context* (HTTPS). A self-signed certificate
works, but every phone has to install and trust it first — clunky on
iOS, genuinely painful on Android.

**The fix OPTIBubble ships: a publicly-trusted certificate for a name that
points at your own LAN.** The app contains a tiny built-in Let's Encrypt
client (no certbot, nothing to install) that proves control of a **free
`yourclass.duckdns.org`** subdomain via the **DNS-01 challenge** and issues a
real, browser-trusted certificate for it.

Why this gives every phone the live camera with **no per-user setup**:

```
duckdns.org  :  yourclass.duckdns.org  →  192.168.1.20   (your PC, private LAN IP)
Let's Encrypt:  issues a cert for "yourclass.duckdns.org"  (trusted by every browser)
phones       :  scan QR B → https://yourclass.duckdns.org:5443/scan/…
                → resolves straight to your PC on the local Wi-Fi 🔒 live camera
```

* **No ports to open, no router changes** — the DNS-01 challenge proves domain
  ownership through a TXT record, so your PC never has to be reachable from
  the internet.
* **Scans never leave the room** — only the (one-time) issuance and occasional
  renewal talk to the internet; photos and results stay on the LAN.
* **Automatic renewal** ~30 days before the 90-day certificate expires.

**Setup — one minute, once, on this PC only.** Settings →
*Live camera (HTTPS)* → mode **Trusted** → paste your free
[duckdns.org](https://www.duckdns.org) domain + token → press
**Set up the live camera**. A guided checklist shows live progress
(*checking your setup → contacting Let's Encrypt → publishing the DNS
challenge → waiting for DNS → issuing → activating*) and the certificate
**activates itself — no restart**. The pre-flight step even catches the classic
mistake (the domain pointing at the wrong IP) and tells you the exact fix.
Afterwards the Scan & Serve page drops to a **single “Scan to grade” QR code**
with a *Trusted HTTPS · yourclass.duckdns.org* status chip. See
[`setup.md` §4.5](setup.md) for the full walkthrough.

**No internet on this network?** Leave HTTPS mode on *Local CA* (users
scan code A once to trust your PC; Android users should use Firefox), or rely
on the native-camera upload fallback that works everywhere regardless.

---

## 🧠 The OMR engine

1. **Validate** — resolution and exposure checks with actionable error codes
   (`LOW_RES`, `TOO_DARK`, `TOO_BRIGHT`).
2. **Detect** — a **three-pass** anchor search, most-strict first so a clean photo is
   never disturbed: (1) CLAHE + Otsu square-contour candidates filtered by size,
   aspect and fill ratio; (2) adaptive Gaussian threshold + a morphological close
   that reconnects anchor squares split by glare or a hard shadow; (3) relaxed
   filters for folded or low-contrast corners. The 4-marker set whose quadrilateral
   matches the page aspect and equal-diagonal geometry wins.
3. **Flatten** — perspective transform onto a canonical raster (width configurable,
   default 1600 px). A post-warp anchor darkness check catches bad alignments
   (`WARP_FAILED`).
4. **Measure** — mean grey inside the inner disc of every bubble (inner-sampling
   radius configurable, so printed outlines never count).
5. **Normalise** — every bubble is scored *relative to its own row*: the
   brightest sibling is unmarked paper under the same lighting, and the printed
   anchors define black — so scores sit on a stable 0 (= empty) … 1 (= ink)
   scale whether the photo is bright, dim or half in shadow.
6. **Verify** — connected-component analysis on each “filled” bubble: a real
   stroke is one large blob; a smudge is many tiny ones → review, not grade. The
   same measure also **auto-resolves** a mark that reads light (a light pen or pencil
   that still fills the bubble) but is otherwise a solid, clearly-winning stroke —
   it is graded instantly instead of being sent for review, so you only ever
   eyeball genuinely ambiguous bubbles.
7. **Decide** — per question:
   * top density `< t_blank` → **blank**
   * top density `< t_fill` → **faint** (stray mark)
   * second density ≥ `max(t_fill, top × multi_ratio)` → **double-marked**
   * top density `< faint_upper` → **faint** (light pen / partial erase)
   * otherwise → confident, auto-graded
8. **Export** — verified sheets append to CSV instantly; flagged sheets wait for you.

Every threshold above is a live control in **Settings → OMR engine**.

---

## 📁 Data & CSV schema

Everything is stored under `~/OPTIBubbleData/` (shown in the sidebar):

```
~/OPTIBubbleData/
├── settings.json
├── master_results.csv
└── tests/T123456/
    ├── test.json       # config + exact sheet geometry
    ├── sheet.pdf       # printable answer sheet
    ├── sheets/         # every received photo (audit trail)
    ├── review/         # pending reviews + cropped evidence images
    └── results.csv     # final results for this test
```

`results.csv` columns:

| Column | Meaning |
|---|---|
| `Timestamp` | when the sheet was finalised |
| `Student_ID` | read from the bubble ID grid (editable in review) |
| `Test_ID`, `Test_Title` | session identifiers |
| `Total_Score`, `Max_Score`, `Percent` | the grade |
| `Detailed_Answers_JSON` | full per-question breakdown: answers, correctness, flags, confidence |
| `Status` | `Verified` (auto or human-confirmed) or `Flagged` |
| `Source_Image` | path to the original photo for audit |

---

## ⚙️ Advanced settings (fine-tuning)

| Setting | Default | What it does |
|---|---|---|
| Bubble fill threshold `t_fill` | 0.34 | dark-pixel ratio above which a bubble counts as filled |
| Blank threshold `t_blank` | 0.14 | below this, no mark at all |
| Faint-mark ceiling | 0.65 | fills between `t_fill` and this are flagged “faint” |
| Double-mark ratio | 0.62 | 2nd-darkest ÷ top above this → flagged “multi” |
| Binarisation offset | 0 | shift the Otsu cut-off — raise it for light-pencil classes |
| Flatten width | 1600 px | resolution of the corrected page |
| Auto-accept blanks | off | blank = wrong without appearing in review |
| Save flattened pages | off | keep a top-down PNG per sheet (debug / audit) |
| JPEG quality / capture width | 92 / 2048 | phone-side capture quality |
| Port / bind / max upload | 5000 / 0.0.0.0 / 30 MB | server controls |
| Master CSV | on | append everything to one combined file |

Changes apply to the next processed sheet and persist in `settings.json`.

---

## ❓ FAQ

The same FAQ is built into the app (**Help & FAQ**).

<details>
<summary><b>How do users scan their sheets?</b></summary>

Start the server on the <b>Scan & Serve</b> page, then open the QR link with any phone camera. The scanner runs in the browser — no app install, no account, no internet. The phone just needs to share this computer's Wi-Fi.
</details>
<details>
<summary><b>The phone shows a camera error / black view — why?</b></summary>

Browsers only allow the in-page camera on HTTPS pages. The zero-setup fix is **Trusted HTTPS mode** (see the section above): a built-in Let's Encrypt client issues a real certificate for your free `*.duckdns.org` domain, so every phone gets the live camera after one QR scan — no installs. Fully offline instead? Use *Local CA* mode: users scan **code A** once to trust your PC (iOS: profile install; Android: use Firefox), then **code B** opens the live scanner. And if neither is set up, the scanner automatically falls back to the phone's native camera app — those photos are graded exactly the same.
</details>
<details>
<summary><b>What pens or pencils work best?</b></summary>

Black or dark blue ballpoint gives the highest confidence; dark pencils (2B) work too. Ask users to fill bubbles completely and erase cleanly — faint or half-erased marks are <i>intentionally</i> flagged for your review instead of being silently misgraded.
</details>
<details>
<summary><b>What gets flagged for review?</b></summary>

(1) No bubble filled — unanswered. (2) Several bubbles filled — double-marked, invalid. (3) A mark whose darkness falls inside the ambiguity band — faint or partially erased. All three thresholds are tunable in <b>Settings → OMR engine</b>, and you can auto-accept blanks to reduce review load.
</details>
<details>
<summary><b>A sheet was rejected — what now?</b></summary>

The phone shows the exact reason and a hint. Common causes: a corner square hidden or cut off, the photo too dark or blurry, or a very steep angle. Flatten the sheet, avoid shadows, shoot from directly above, include all four black corner squares.
</details>
<details>
<summary><b>Where is my data stored? (privacy)</b></summary>

Everything stays on this computer — default folder <code>~/OPTIBubbleData</code>. Each test keeps its PDF, every received photo, crop evidence and <code>results.csv</code>. Nothing is ever uploaded anywhere; the only network traffic is photos travelling over your own LAN from phones to your PC.
</details>
<details>
<summary><b>Can I print with any printer and paper?</b></summary>

Yes — any inkjet or laser printer on plain A4 or US-Letter paper, at 100% scale (“Actual size”, not “Fit to page”).
</details>
<details>
<summary><b>How many questions fit on one sheet?</b></summary>

Up to <b>102</b> on a single A4 page (1–3 columns of up to 34 rows), with 2–5 options each. Letter paper holds slightly fewer rows; the layout adapts automatically.
</details>
<details>
<summary><b>Can several phones scan at once?</b></summary>

Yes — the server accepts simultaneous uploads and grades in parallel with two worker threads.
</details>
<details>
<summary><b>Does it work offline?</b></summary>

Completely. The desktop app, grading engine, mobile page and fonts are all served from your machine over the local network.
</details>
<details>
<summary><b>How do I get results into Excel?</b></summary>

Open the <b>Results</b> page → <i>Export CSV copy</i>. The <code>Detailed_Answers_JSON</code> column contains the full per-question breakdown for deep dives.
</details>
<details>
<summary><b>The QR code doesn't open anything.</b></summary>

Check that (1) the phone is on the same Wi-Fi, (2) your firewall allows Python/OPTIBubble on port 5000, (3) the URL under the QR matches this computer's IP (switch the IP selector if you have several adapters). On some routers “AP/client isolation” blocks phone→PC traffic — disable it in the router admin.
</details>
<details>
<summary><b>Can I run this as a native desktop app?</b></summary>

Yes — the bundled Tauri 2 shell (<code>src-tauri/</code>) wraps the same UI in a native window and produces installers. See <a href="#-native-app-tauri-optional">Native app (Tauri)</a> above.
</details>

---

## 🛠 Troubleshooting

| Symptom | Fix |
|---|---|
| `Port 5000 already in use` | Change the port in **Settings → Local server** (macOS: AirPlay Receiver also uses 5000), or `python main.py --port 5050` |
| Phone can't reach the link | Same network? Firewall? Wrong IP in the selector? AP-isolation disabled? |
| Everything grades as blank | Print at 100% scale; use the generated PDF; raise “Binarisation offset” slightly for very light pencils |
| Too many faint flags | Lower the “Faint-mark ceiling” or raise `t_fill` in Settings |
| Camera page shows a black preview | Use the 🖼️ upload button — the native-camera fallback always works |
| Weird layout when printing | Disable “Fit to page” / “Shrink to printable area” in the print dialog |

---

## 📁 Project structure

```
OPTIBubble/
├── frontend/                 # React + Tailwind + Motion SPA source
│   ├── src/components/ui.jsx  # Regmark v2 design system (full state matrix)
│   ├── src/pages/             # Dashboard · Setup · Serve · Review · Results · Settings · Scanner
│   └── vite.config.js
├── main.py                  # launcher (app / --serve / --demo / --selftest)
├── selftest.py              # end-to-end verification suite (85 checks)
├── setup.md                 # setup · local builds · GitHub · Actions releases
├── make_assets.py           # regenerates logo/brand assets from bundled fonts
├── requirements.txt
├── .github/workflows/main.yml  # CI on push/PR + full release matrix on tags
├── packaging/flatpak/       # Flatpak manifest · desktop file · metainfo
├── tools/otf2ttf.py         # wordmark OTF→TTF converter (ReportLab embeds)
├── src-tauri/               # Tauri 2 native shell (optional build)
│   ├── src/main.rs          # spawns the Python engine, opens the window
│   ├── tauri.conf.json
│   └── icons/
├── optibubble/
│   ├── config.py            # test config + all advanced fine-tune settings
│   ├── layout.py            # single source of truth for sheet geometry (mm)
│   ├── sheet_generator.py   # ReportLab PDF generator (QR, anchors, ID grid)
│   ├── omr_engine.py        # OpenCV pipeline + confidence/flagging model
│   ├── server.py            # embedded Flask app (desktop UI + mobile bridge + API)
│   ├── hub.py               # runtime controller (threads, events, receipts)
│   ├── storage.py           # sessions, review queue, CSV export
│   ├── fonts/               # OPTIBubble + Instrument Sans + IBM Plex Mono + Instrument Serif (bundled)
│   └── web/                 # app.html/css/js · scan.html · woff2 · brand images
└── docs/                    # screenshots & pipeline figures
```

---

## 💻 Platform support

| OS | Status | Notes |
|---|---|---|
| Windows 10/11 | ✅ primary | Defender firewall prompt on first server start |
| macOS 12+ | ✅ | Change port if AirPlay Receiver occupies 5000 |
| Linux (X11/Wayland) | ✅ | `python3-tk` not required — the UI is web-based |

---

## 🔒 Privacy

OPTIBubble was built for exactly one privacy posture: **user data never leaves the
room.** There is no telemetry, no update ping, no account server, no CDN in the mobile
page — the entire system runs from this computer and the Wi-Fi router on your network.

---

## 🧪 Development

```bash
pip install -r requirements-dev.txt
python selftest.py              # end-to-end suite (85 checks)
python make_assets.py           # regenerate brand assets from the bundled fonts
python tools/otf2ttf.py         # re-convert the wordmark OTF → embeddable TTF
python docs/shot_pipeline.py    # rebuild the pipeline figure
python docs/shot_web.py         # headless-browser UI screenshots (Playwright)
```

---

## 🙏 Credits & licences

- **OPTIBubble** — the wordmark typeface, bundled for the brand/logo.
- **[Instrument Sans](https://fonts.google.com/specimen/Instrument+Sans)** — UI/web font.
- **[IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono)** — micro-labels / instrument silkscreen.
- **[Instrument Serif](https://fonts.google.com/specimen/Instrument+Serif)** — one serif accent per screen.
- Built with [OpenCV](https://opencv.org), [ReportLab](https://www.reportlab.com), [Flask](https://flask.palletsprojects.com), [qrcode](https://github.com/lincolnloop/python-qrcode), [Pillow](https://python-pillow.org), [PyMuPDF](https://pymupdf.readthedocs.io), [Tauri](https://tauri.app).
- Application code: **GPL-3.0** — see [LICENSE](LICENSE). The bundled fonts keep their own licences (Instrument Sans / IBM Plex Mono / Instrument Serif: SIL OFL; OPTIBubble: freeware).

<div align="center">

**OPTIBubble — Scan. Grade. Done.**

</div>
