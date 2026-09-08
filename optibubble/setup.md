# OPTIBubble — Setup, Build & Release Guide

From a fresh clone to published installers for **Windows, macOS and Linux
(AppImage · deb · RPM)** — step by step.

> **TL;DR** — `pip install -r requirements.txt` → `python main.py`.
> Native installers: push a tag like `v1.0.0` and GitHub Actions builds them all.

---

## Contents

1. [Prerequisites](#1--prerequisites)
2. [Development setup](#2--development-setup-any-os)
3. [Uploading to GitHub](#3--uploading-to-github)
4. [Building locally](#4--building-locally)
5. [Releasing via GitHub Actions (`main.yml`)](#5--releasing-via-github-actions)
6. [The complete `main.yml` (verbatim)](#6--the-complete-mainyml-verbatim)
7. [Version bumping checklist](#7--version-bumping-checklist)
8. [Version bumping checklist](#8--version-bumping-checklist)
9. [Troubleshooting](#9--troubleshooting)

---

## 1 · Prerequisites

| | Requirement | Why |
|---|---|---|
| Always | **Python 3.9+** | the entire engine + UI runs on it |
| Always | Git | pushing to GitHub |
| Optional | **Rust 1.77+** via [rustup](https://rustup.rs) | native Tauri builds only |
| Linux native builds | WebKit dev packages | see [§4.3](#43--linux-prerequisites-for-tauri) |

Node 18+ is needed **once, to build the React SPA** (the desktop app and phone
scanner are a single Vite-built SPA served by the engine). A packaged installer
ships the built SPA, so end users never need Node.

## 2 · Development setup (any OS)

```bash
git clone https://github.com/<you>/OPTIBubble.git
cd OPTIBubble

# front-end (Node 18+): build the React SPA once — the engine serves the result
cd frontend && npm install && npm run build && cd ..

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python selftest.py                 # end-to-end suite — 85 checks, all green
python main.py                     # app opens at http://127.0.0.1:8090
```

Handy commands while developing:

```bash
python main.py --demo              # seed a ready-to-play demo test
python main.py --serve T123456     # headless serve of a saved test
python main.py --port 5050         # run on another port
python make_assets.py              # regenerate logo/icon/hero from bundled fonts
python tools/otf2ttf.py            # re-convert the wordmark OTF → TTF (rare)
python docs/shot_pipeline.py       # rebuild docs/pipeline.jpg
```

## 3 · Uploading to GitHub

```bash
cd OPTIBubble
git init
git add .
git commit -m "OPTIBubble v1.0.0"
git branch -M main

# create an empty repo on github.com/<you>/OPTIBubble first, then:
git remote add origin git@github.com:<you>/OPTIBubble.git
git push -u origin main
```

Or with the GitHub CLI (creates the repo for you):

```bash
gh repo create OPTIBubble --public --source=. --push
```

`.gitignore` already excludes runtime data (`OPTIBubbleData/`), caches and Rust
build outputs. Verify with `git status` that **no personal data** is committed.

## 4 · Building locally

### 4.1 · Python app (all platforms)

Nothing to compile — it runs from source. `python main.py` is the product.

### 4.2 · Native desktop app (Tauri 2)

```bash
cargo install tauri-cli --version "^2"     # once
cargo tauri dev                            # native window (spawns the engine)
cargo tauri build                          # installers → src-tauri/target/release/bundle/
```

The shell launches `python3 main.py --no-browser` and reads the engine's real
port from a `--port-file`, so it opens the window at whatever port the engine
actually bound (it falls back automatically if 8090 is occupied). Building
from source on a dev machine needs Python + `pip install -r requirements.txt`;
a release installer freezes the engine with PyInstaller (§4.6) so end users
need nothing installed.

### 4.3 · Linux prerequisites for Tauri

```bash
sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
```

Bundles produced on Linux: **AppImage, deb, RPM** (select with
`cargo tauri build --bundles appimage,deb,rpm`).

### 4.4 · The mobile-camera HTTPS problem — what works and why

Mobile browsers hard-gate the in-page camera (`getUserMedia`) behind a *secure
context* — there is no JavaScript workaround. The realistic options, ranked:

| Approach | Phone-side friction | Needs internet? | Verdict |
|---|---|---|---|
| **Trusted cert via Let's Encrypt DNS-01 + free DuckDNS domain** (built in: Settings → HTTPS mode → *Trusted*) | **none** — camera works in every browser, one QR scan | once at issuance (auto-renews ~30 days before expiry) | ✅ best UX — the Home Assistant pattern for local HTTPS |
| Built-in local CA + code A install (built in, offline mode) | iOS: install profile + trust toggle (once). Android: Firefox or fallback | never | ✅ keep for fully offline networks |
| Native-camera fallback (upload button) | none, but no live viewfinder | never | ✅ always available, automatic |
| `chrome://flags` unsafely-treat-origin-as-secure | per-device flag fiddling | never | ❌ worse than a certificate |
| ngrok / cloud tunnels | none | always on, traffic leaves the LAN | ❌ violates the no-cloud posture |
| USB port-forward to `localhost` | cable + dev tools | never | ❌ not practical at scale |

#### How Trusted HTTPS mode actually works

The browser demands a certificate *it already trusts* — so OPTIBubble gets a
real one from Let's Encrypt, for a name **you** own (a free
`yourclass.duckdns.org` subdomain) that points at your **private LAN IP**:

1. You register the subdomain at duckdns.org and set its IP to this PC
   (e.g. `192.168.1.20`). DuckDNS has an "update IP" page — pasting the LAN
   IP is fine; public exposure is **not** required.
2. On **Issue certificate**, the built-in ACME client (`optibubble/acme.py`,
   ~250 lines on `cryptography`, no certbot):
   - registers a Let's Encrypt account (key stored in `<data>/certs/`),
   - opens an order for `yourclass.duckdns.org` and picks the **DNS-01**
     challenge,
   - asks DuckDNS (via your token) to publish the one-time
     `_acme-challenge` **TXT record**,
   - waits until the record is visible via DNS-over-HTTPS,
   - finalises the order with a CSR and stores
     `trusted-fullchain.pem` + `trusted-key.pem` locally.
3. From then on the HTTPS bridge serves that certificate. Phones that scan
   QR B open `https://yourclass.duckdns.org:5443/…` — the name resolves to
   your LAN IP, the cert chains to a root every device already trusts, and
   the browser grants the live camera with **zero prompts**.

**Why no router changes:** DNS-01 proves domain ownership through the TXT
record alone; Let's Encrypt never connects to your PC. Nothing is forwarded,
nothing is reachable from outside, and the scan traffic itself never
leaves the Wi-Fi — only the one-time issuance and the ~quarterly renewal
touch the internet.

**Renewal:** certificates last 90 days; the engine re-issues automatically
when fewer than 30 days remain (seen in the Scan & Serve log). Your
DuckDNS name keeps pointing at the PC — if the PC's LAN IP ever changes,
update it once at duckdns.org (no new certificate needed; the cert is for the
*name*, not the IP).

#### Step-by-step (one minute, once)

1. Sign in at [duckdns.org](https://www.duckdns.org) (any GitHub/Google/etc.
   account), create a subdomain, e.g. `myclass`, set its IP to this PC's LAN
   address, and copy your **token** from the top of the page.
2. OPTIBubble → **Settings → Live camera (HTTPS)** → mode
   **Trusted · recommended** → fill *domain*, *token*, *email* → press
   **Set up the live camera**. A guided checklist shows live progress with
   elapsed time (checking your setup → contacting Let's Encrypt → publishing
   the DNS challenge → waiting for DNS → issuing → activating). Takes ≤ 3 min,
   dominated by DNS propagation. The certificate **activates itself** — no
   server restart, no extra clicks.
3. Done. The Scan & Serve page now shows a **single “Scan to grade” QR code**
   at `https://myclass.duckdns.org:5443/…` with a
   *Trusted HTTPS · myclass.duckdns.org* status chip; the certificate-install
   code disappears — it isn't needed.

If anything is wrong, the wizard stops at the failing step with a plain-language
fix — e.g. *“myclass.duckdns.org points at 84.x.x.x, but this PC is
192.168.0.15 — open duckdns.org, set the IP to 192.168.0.15, press Start
again”*. Nothing to interpret, nothing to restart.

**Verify it worked:** open the QR-B URL on any phone (or this PC) —
the padlock is clean with no warnings and the scanner shows the
“🔒 Secure camera” chip. If anything fails, the log names the step (bad token,
unreachable duckdns.org, propagation timeout) and the system simply keeps
running the Local-CA HTTPS + HTTP fallbacks — nothing breaks.

**Security notes:** the DuckDNS token is stored in plain text in
`settings.json` (it can only update *your* subdomain's IP/TXT records — keep
the file private anyway); the certificate key lives in `<data>/certs/`;
and phones never need the token or any configuration.

### 4.6 · Bundling — installers ship the whole engine (no Python needed)

Release installers freeze the engine with PyInstaller (`optibubble.spec`) into
a single `optibubble-engine` binary (~100–150 MB with OpenCV) that the Tauri
shell spawns automatically — end users need **nothing** installed. The same
`main.rs` falls back to `python3 main.py` on developer machines, so both modes
coexist:

```bash
pip install -r requirements.txt pyinstaller
pyinstaller optibubble.spec --distpath src-tauri/engine --noconfirm
cargo tauri build        # bundles src-tauri/engine/* into the installers
```

The installers are self-contained — the frozen engine is bundled with them, so
end users need nothing installed. Notes:

- the frozen engine's first launch takes a few extra seconds (one-file
  extraction); subsequent requests are normal speed;
- keep `excludes` in the spec current when you add heavy dev dependencies;
- PyOxidizer was considered and rejected (unmaintained, no current-Python
  support); a full Rust port would shrink the binary but means rewriting a
  tested engine — the frozen route keeps one codebase.

## 5 · Releasing via GitHub Actions (manual — no tag needed)

The repo ships **one workflow**, `.github/workflows/main.yml`, that does both
CI and releases. Releases are **triggered by hand** from the Actions tab — there
is **no git-tag requirement**. You type a release version (required) and notes
(optional) when you trigger it.

| Trigger | What runs | Duration |
|---|---|---|
| **Actions → Build & Release → Run workflow** | full release — every installer + `SHA256SUMS`, attached to a **draft** GitHub Release | 10–25 min |

**When you trigger a release you must fill in two fields:**

| Input | Required? | What it does |
|---|---|---|
| `release_version` | **yes** | e.g. `2.0.3`. Creates the tag + draft release `v2.0.3`, and stamps this version into the app so every installer reports it (via `tools/sync_version.py`). |
| `release_notes` | no | The body of the release (markdown). Leave blank for a short default. |

**Artifacts per release** — the builder jobs run **in parallel**:

| Runner | Bundle(s) you get |
|---|---|
| `ubuntu-22.04` (job ×3) | `.deb` · `.rpm` · `.AppImage` — **three separate parallel jobs** |
| `windows-latest` | `.msi` · NSIS `-setup.exe` |
| `macos-latest` (job ×2) | `.aarch64.dmg` (M-series) · `.x64.dmg` (Intel) |
| — (after the above finish) | `SHA256SUMS` checksum file |

**Cutting a release — the steps:**

1. (Optional) run the self-test locally so you only trigger a green build:
   `python selftest.py`
2. Go to the **Actions** tab → **Build & Release** → **Run workflow**.
3. Enter `release_version` (e.g. `2.0.3`) and, if you like, `release_notes`. **Run workflow.**
4. Watch it build. `prepare-release` creates the draft `v2.0.3` first, then the
   installer jobs run in parallel and upload to it. The `checksums` job
   runs last to attach `SHA256SUMS`. (You do **not** run `git tag` yourself.)
5. Open **Releases** → the draft **“OPTIBubble v2.0.3”** has every installer +
   the checksum file. Review/edit the notes, then press **Publish**.

> The release is a **draft** on purpose — nothing is public until you publish it.
> No secrets or signing keys are required for unsigned builds. To sign later:
> Windows → `TAURI_SIGNING_PRIVATE_KEY` secrets (Tauri docs); macOS notarization →
> `APPLE_CERTIFICATE`/`APPLE_ID` secrets. The `SHA256SUMS` file is what users run
> `sha256sum -c` against (README → Download).
>
> **Caching:** the workflow reuses things that haven't changed — npm deps, pip
> packages, the `src-tauri` Cargo build, and the frozen Python engine. Rebuilding
> the same code twice is much faster than the first time; changing the engine
> code or frontend invalidates those caches.

## 6 · The release workflow (`main.yml`)

> The authoritative file is **`.github/workflows/main.yml`** — keep the two in
> sync by copying the file rather than the notes below. A summary of the jobs:

| Job | Runs when | Purpose |
|---|---|---|
| `selftest` | manual dispatch | installs deps, builds the React SPA, runs `python selftest.py` (the release gate) |
| `prepare-release` | manual dispatch | creates the draft release + tag `v<version>` (single point, avoids upload races) |
| `tauri` (matrix) | manual dispatch | builds every installer **in parallel**: Linux `.deb`/`.rpm`/`.AppImage`, macOS dmg ×2, Windows MSI+NSIS |
| `checksums` | manual dispatch | downloads all assets and attaches `SHA256SUMS` |

Key points why it's robust:

- The **React SPA is built before the engine is frozen** (`optibubble/web/dist`
  is a build artifact, not committed), so installers ship the real React UI.
- The **Python engine is frozen before `cargo check`/`tauri build`**, because the
  Tauri build script resolves the `engine/*` resource glob at build time —
  missing it was the previous build-killer. (`src-tauri/engine/.gitkeep` is
  committed so the glob resolves on a fresh clone / local `cargo build`.)
- The **frozen engine + Cargo build are cached** by source hash, so an unchanged
  engine is restored instead of rebuilt, and a version bump alone doesn't
  recompile all of Rust.
- The Linux `.deb`/`.rpm`/`.AppImage` are three **separate parallel jobs** so
  they finish at the same time instead of one-after-another.

## 7 · Version bumping checklist

- [ ] `python tools/sync_version.py X.Y.Z` (updates every manifest at once;
      the self-test fails if they ever drift)
- [ ] `cd src-tauri && cargo update -p optibubble`
- [ ] commit & push the branch, then trigger a release from **Actions →
      Build & Release → Run workflow** (no `git tag` needed — the workflow
      creates the `vX.Y.Z` tag and draft release for you)

## 8 · Troubleshooting

| Symptom | Fix |
|---|---|
| `cargo tauri` not found | `cargo install tauri-cli --version "^2"`; ensure `~/.cargo/bin` is on `PATH` |
| Linux: `webkit2gtk-4.1 not found` | install the §4.3 packages (CI runners already do) |
| Actions release has no artifacts | the release jobs only run on a **manual** dispatch — go to **Actions → Build & Release → Run workflow** and fill in the version (you must have pushed your commit first) |
| Tauri window opens to an error page | the Python engine failed to start — run `python main.py` once to see why |
| Port 8090 busy | The default is 8090 (not 5000, which macOS AirPlay Receiver occupies) — `python main.py --port 8091` (HTTPS bridge: `https_port` in Settings) |
| Phone still warns after certificate install | Android Chrome ignores user CAs — use Firefox, or the 🖼️ upload fallback; also check the IP selector matches the phone's network |
| HTTPS bridge not starting | port 5443 busy or `cryptography` missing → see the log card; the HTTP scanner + native-camera fallback keep working |
| Self-test fails locally | reinstall deps (`pip install -r requirements.txt`) — OpenCV/numpy version mismatch is the usual cause |

---

**Next:** [`README.md`](README.md) — features, usage, the OMR engine and the
Regmark design language.
