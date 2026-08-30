<div align="center">

<img src="docs/hero.png" alt="OPTIBubble" width="860"/>

**Local computer-vision OMR grading with a zero-install mobile scanner.**

Print dynamic answer sheets → students photograph them with **any phone browser** over Wi-Fi → OpenCV grades them on **your** computer → ambiguous marks land in a review queue → export to CSV.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Tauri 2](https://img.shields.io/badge/native%20shell-Tauri%202-FFC131?logo=tauri&logoColor=white)](#-native-app-tauri-optional)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-425466)](#-platform-support)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-22C55E.svg)](LICENSE)
[![Privacy](https://img.shields.io/badge/privacy-100%25%20local%2C%20no%20cloud-3B82F6)](#-privacy)
[![Self-test](https://img.shields.io/badge/self--test-60%2F60%20green-22C55E)](#-development)

*No Scantron hardware. No cloud subscription. No app store. No student data leaving the room.*

**Wordmark set in [OPTIBubbleDoubleBold](https://www.ffonts.net/OPTIBubbleDoubleBold.font) · UI set in Open Sans** — both bundled.

</div>

---

## 🎨 Design language — *Regmark*

The interface is built on **Regmark**, an in-house design language themed after
the product itself: *paper, ink, and the grading pen*.

| Token | Value | Use |
|---|---|---|
| Carbon | `#0C0D11 → #22252E` | flat surface ladder — one uniform page, cards lift via lighter derivatives |
| Paper | `#F4F2EB` family | the light theme — warm answer-sheet stock |
| Persimmon | `#FF5A2D` | the single brand accent — the grading pen |
| Ink | `#EAEBEF / #191A1F` | typography |

Rules of the system: **flat surfaces with zero resting shadows and zero
decorative borders; 4 px corners on shells with pill badges and toggles;
inputs read through contrasting fills instead of borders; gradient hairline
separators; tabular numerals everywhere data lives; and the *registration
mark* — corner brackets borrowed from the sheet's alignment anchors — as the
focus and selection device.** Typography is Open Sans (UI) with the
OPTIBubbleDoubleBold wordmark — both bundled and subsetted, fully offline.

On paper, the sheet brand colour is **#2e5a99** (white on dark backgrounds),
applied to the embedded wordmark and the header rule.

---

## ✨ Features

| | |
|---|---|
| 🖨 **Dynamic sheet generator** | 2–102 questions, 2–5 options (A–B … A–E), auto multi-column layout, up to 10-digit student-ID grid, session QR code, four machine-vision alignment anchors. A4 & US Letter. |
| 📊 **System info & in-app self-test** | Settings → System shows version, Python/OpenCV/platform, storage used, network + HTTPS status and lifetime counters — plus a button that runs the full 60-check suite and prints the verdict in-app. |
| 🔑 **Answer key printing** | A one-page teacher key PDF — grid of Q#→letter plus a compact string — generated with every test and **auto-refreshed when the key changes**. One button next to the sheet PDF on Scan & Serve. |
| ✏️ **Sheet designer** | Editable title, custom instructions, header text size (80–140 %), wordmark side and **handwritten write-in fields** (Name/Class/Date…, ignored by the scanner) — all inside the header, with **auto-shrink instead of overlap** and a header layout that is *proven* collision-free before the PDF is written. The OPTIBubble wordmark prints in **#2e5a99** (white on dark media). |
| 🗂 **Test management** | Every test keeps its own sheets, review queue and CSV. Open, **edit** (title/subject/key/design — the sheet PDF regenerates), **delete** with confirmation, and see which test is *active* via context chips on Serve/Review/Results. |
| 🎲 **Auto answer key** | Leave the key empty and a complete key is generated automatically — create a test in seconds, edit the key any time, even after sheets are printed. |
| 🔍 **Evidence cards & lightbox** | Every flagged item shows a framed, legible evidence crop (scrollable for wide strips); click to inspect full-screen, Esc to close. |
| 🔑 **Print-first workflow** | Create and print sheets with a partial (or empty) answer key; finish the key later on the Scan & Serve page — grading scores whatever is already defined. |
| 📱 **Mobile web bridge + HTTPS** | A QR link opens a premium scanner page — live viewfinder, torch, quality check, instant feedback. Two HTTPS modes: **Trusted (zero student setup)** — built-in Let's Encrypt client issues a publicly-trusted cert for your free `*.duckdns.org` domain via DNS-01, so the camera just works in any browser; or **Local CA (fully offline)** — students scan code A once. iOS & Android. |
| 🔍 **Real OMR pipeline** | Otsu binarisation → anchor-square contour detection (on a downscaled raster for speed) → perspective warp → per-bubble dark-pixel-density analysis with a confidence model. A typical photo grades in **~80 ms** on a laptop CPU; long sessions are bounded (capped receipts, cached CSV reads, no leaked queues). |
| ⚑ **Confidence flagging** | Unanswered, double-marked and faint/partially-erased marks are flagged and shown as zoomable crops — one click to override and export. |
| 🖥 **Modern desktop UI** | A premium web app served by the engine itself (dashboard → review → export), wrapped in a native window by the bundled **Tauri 2** shell — or just run it in your browser. |
| 📊 **Live CSV export & analytics** | Every verified sheet appends instantly to `results.csv` (+ optional master CSV). Results view adds a score-distribution histogram, ID filtering, and duplicate-submission warnings. |
| ⌨️ **Keyboard review** | Fly through flagged sheets: ←/→ move between items, 1–5 pick an option, B blank, Enter confirm. |
| ⚙️ **Advanced fine-tuning** | Every engine threshold — fill, blank, ambiguity band, double-mark ratio, binarisation offset, warp resolution — plus camera quality and server options, live in Settings. |
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

| Dashboard | New test & answer key |
|---|---|
| ![Dashboard](docs/screenshots/01-dashboard.png) | ![Setup](docs/screenshots/02-setup.png) |

| Scan & Serve (magic link) | Review queue with evidence crops |
|---|---|
| ![Serve](docs/screenshots/03-serve.png) | ![Review](docs/screenshots/04-review.png) |

| Results & CSV export | Mobile scanner (phone browser) |
|---|---|
| ![Results](docs/screenshots/05-results.png) | ![Mobile](docs/screenshots/08-mobile-scanner.png) |

<details>
<summary><b>More — settings, FAQ, generated sheet, simulated phone photo</b></summary>

| Settings (every threshold live) | Help & FAQ (built-in) |
|---|---|
| ![Settings](docs/screenshots/06-settings.png) | ![Help](docs/screenshots/07-help.png) |

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

### 2 · Run the self-test (recommended)

```bash
python selftest.py
```

Builds a sheet, simulates filled bubbles (pen strokes, partial marks), synthesises phone
photos (perspective jitter, brightness gradients, sensor noise, JPEG artefacts) across
random seeds, and asserts exact scores, flag types, student-ID reads, the full HTTP
stack and the < 3 s latency budget — **60 checks, expect all green**.

### 3 · Launch

```bash
python main.py          # opens the desktop app in your browser
```

### 4 · Run your first test (3 minutes)

1. **New Test** — set title, questions, options; click through the answer-key cells
   (or paste `1:A 2:C …` / `ACBD…`, or randomise). **Create test & generate sheet**.
2. **Scan & Serve** — open the sheet PDF and print at **100 % (“Actual size”)**.
   Hand out the sheets. Press **Start server** — the QR magic link appears.
3. Students scan it with the phone's regular camera; the scanner opens in the browser.
   They photograph the sheet with all four corner squares inside the frame.
4. Results stream in live. Confident sheets are graded and exported instantly;
   anything ambiguous lands in **Review Queue** with a cropped image of the disputed
   bubble — pick the right option (or *Blank*), hit **Confirm & export**.
5. **Results** — export the CSV copy. Done. ☕

> **Classroom tip:** phones and the computer must share a Wi-Fi network (a laptop
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

The shell detects whether the engine is already running on `127.0.0.1:5000`,
spawns `python main.py --no-browser` if not, waits for it, opens the native
window, and shuts the engine down on exit. No Node.js toolchain needed — the
frontend is plain HTML/CSS/JS served by the engine.

➡ **Full instructions — local builds, GitHub upload, Actions release matrix,
Flatpak/RPM recipes — live in [`setup.md`](setup.md).**

---

## 📠 The mobile scanner

Served entirely from your PC — the page and its Open Sans fonts are bundled, so it
works with **zero internet access**.

* Live viewfinder with corner-bracket alignment overlay and guidance hints
* Torch button (where supported)
* **Client-side quick check** before upload: exposure, blur and corner-marker presence
* Instant feedback: animated score card, or a friendly *“sent for teacher review”*
* Falls back to the phone's **native camera app** (capture/upload) where the browser
  blocks the in-page camera — common on plain-HTTP LAN addresses — so scanning works
  on *any* device

---

## 🔒 Trusted HTTPS — the live camera with zero student setup

**The problem.** Mobile browsers only allow the in-page camera
(`getUserMedia`) inside a *secure context* (HTTPS). A self-signed certificate
works, but every student phone has to install and trust it first — clunky on
iOS, genuinely painful on Android.

**The fix OPTIBubble ships: a publicly-trusted certificate for a name that
points at your own LAN.** The app contains a tiny built-in Let's Encrypt
client (no certbot, nothing to install) that proves control of a **free
`yourclass.duckdns.org`** subdomain via the **DNS-01 challenge** and issues a
real, browser-trusted certificate for it.

Why this gives every phone the live camera with **no per-student setup**:

```
duckdns.org  :  yourclass.duckdns.org  →  192.168.1.20   (your PC, private LAN IP)
Let's Encrypt:  issues a cert for "yourclass.duckdns.org"  (trusted by every browser)
phones       :  scan QR B → https://yourclass.duckdns.org:5443/scan/…
                → resolves straight to your PC on the classroom Wi-Fi 🔒 live camera
```

* **No ports to open, no router changes** — the DNS-01 challenge proves domain
  ownership through a TXT record, so your PC never has to be reachable from
  the internet.
* **Scans never leave the room** — only the (one-time) issuance and occasional
  renewal talk to the internet; photos and results stay on the LAN.
* **Automatic renewal** ~30 days before the 90-day certificate expires.

**Setup — one minute, once, on the teacher PC only.** Settings →
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

**No internet in the classroom?** Leave HTTPS mode on *Local CA* (students
scan code A once to trust your PC; Android users should use Firefox), or rely
on the native-camera upload fallback that works everywhere regardless.

---

## 🧠 The OMR engine

1. **Validate** — resolution and exposure checks with actionable error codes
   (`LOW_RES`, `TOO_DARK`, `TOO_BRIGHT`).
2. **Detect** — Otsu binarisation; square contour candidates filtered by size, aspect
   and fill ratio; the 4-marker set whose quadrilateral matches the page aspect and
   equal-diagonal geometry wins.
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
   stroke is one large blob; a smudge is many tiny ones → review, not grade.
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
<summary><b>How do students scan their sheets?</b></summary>

Start the server on the <b>Scan & Serve</b> page. Students open the standard camera app on their phone, point it at the QR code, and the scanner page opens in their browser — no app install, no account, no internet. Everyone just needs to be on the same Wi-Fi network as this computer.
</details>
<details>
<summary><b>The phone shows a camera error / black view — why?</b></summary>

Browsers only allow the in-page camera on HTTPS pages. The zero-setup fix is **Trusted HTTPS mode** (see the section above): a built-in Let's Encrypt client issues a real certificate for your free `*.duckdns.org` domain, so every phone gets the live camera after one QR scan — no installs. Fully offline instead? Use *Local CA* mode: students scan **code A** once to trust your PC (iOS: profile install; Android: use Firefox), then **code B** opens the live scanner. And if neither is set up, the scanner automatically falls back to the phone's native camera app — those photos are graded exactly the same.
</details>
<details>
<summary><b>What pens or pencils work best?</b></summary>

Black or dark blue ballpoint gives the highest confidence; dark pencils (2B) work too. Ask students to fill bubbles completely and erase cleanly — faint or half-erased marks are <i>intentionally</i> flagged for your review instead of being silently misgraded.
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
├── main.py                  # launcher (app / --serve / --demo / --selftest)
├── selftest.py              # 60-check end-to-end verification suite
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
│   ├── fonts/               # OPTIBubbleDoubleBold + Open Sans (bundled, OFL)
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

OPTIBubble was built for exactly one privacy posture: **student data never leaves the
room.** There is no telemetry, no update ping, no account server, no CDN in the mobile
page — the entire system runs from this computer and the Wi-Fi router in your classroom.

---

## 🧪 Development

```bash
pip install -r requirements-dev.txt
python selftest.py              # 60-check end-to-end suite
python make_assets.py           # regenerate brand assets from the bundled fonts
python tools/otf2ttf.py         # re-convert the wordmark OTF → embeddable TTF
python docs/shot_pipeline.py    # rebuild the pipeline figure
python docs/shot_web.py         # headless-browser UI screenshots (Playwright)
```

---

## 🙏 Credits & licences

- **[OPTIBubbleDoubleBold](https://www.ffonts.net/OPTIBubbleDoubleBold.font)** — the wordmark typeface (Castcraft OPTI collection), bundled for the logo.
- **[Open Sans](https://fonts.google.com/specimen/Open+Sans)** by Steve Matteson — UI/web font, [SIL OFL 1.1](https://openfontlicense.org).
- Built with [OpenCV](https://opencv.org), [ReportLab](https://www.reportlab.com), [Flask](https://flask.palletsprojects.com), [qrcode](https://github.com/lincolnloop/python-qrcode), [Pillow](https://python-pillow.org), [PyMuPDF](https://pymupdf.readthedocs.io), [Tauri](https://tauri.app).
- Application code: **GPL-3.0** — see [LICENSE](LICENSE). The bundled fonts keep their own licences (Open Sans: SIL OFL; OPTIBubbleDoubleBold: freeware).

<div align="center">

**OPTIBubble — Scan. Grade. Done.**

</div>
