# OPTIBubble — Setup, Build & Release Guide

From a fresh clone to published installers for **Windows, macOS and Linux
(AppImage · deb · RPM · Flatpak)** — step by step.

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
7. [Flatpak & Flathub details](#7--flatpak--flathub-details)
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

No Node.js toolchain is needed anywhere — the UI is plain HTML/CSS/JS served
by the Python engine.

## 2 · Development setup (any OS)

```bash
git clone https://github.com/<you>/OPTIBubble.git
cd OPTIBubble

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python selftest.py                 # expect: 63/63 checks passed · ALL GREEN
python main.py                     # app opens at http://127.0.0.1:5000
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
build outputs. Verify with `git status` that **no student data** is committed.

## 4 · Building locally

### 4.1 · Python app (all platforms)

Nothing to compile — it runs from source. `python main.py` is the product.

### 4.2 · Native desktop app (Tauri 2)

```bash
cargo install tauri-cli --version "^2"     # once
cargo tauri dev                            # native window (spawns the engine)
cargo tauri build                          # installers → src-tauri/target/release/bundle/
```

The shell launches `python3 main.py --no-browser`, so the target machine still
needs Python + `pip install -r requirements.txt`. For a fully self-contained
binary, freeze the engine with PyInstaller (`pyinstaller --onefile main.py`)
and point `src-tauri/src/main.rs` at the frozen binary name.

### 4.3 · Linux prerequisites for Tauri

```bash
sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
```

Bundles produced on Linux: **AppImage, deb, RPM** (select with
`cargo tauri build --bundles appimage,deb,rpm`).

### 4.4 · Flatpak (local test build)

```bash
sudo apt install flatpak flatpak-builder
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.freedesktop.Platform//24.08 org.freedesktop.Sdk//24.08

flatpak-builder --user --install --force-clean \
  .flatpak-build packaging/flatpak/com.optibubble.app.yml
flatpak run com.optibubble.app

# or bundle a single portable file:
flatpak-builder --repo=.flatpak-repo --force-clean \
  .flatpak-build packaging/flatpak/com.optibubble.app.yml
flatpak build-bundle .flatpak-repo OPTIBubble.flatpak com.optibubble.app
```

### 4.5 · The mobile-camera HTTPS problem — what works and why

Mobile browsers hard-gate the in-page camera (`getUserMedia`) behind a *secure
context* — there is no JavaScript workaround. The realistic options, ranked:

| Approach | Student friction | Needs internet? | Verdict |
|---|---|---|---|
| **Trusted cert via Let's Encrypt DNS-01 + free DuckDNS domain** (built in: Settings → HTTPS mode → *Trusted*) | **none** — camera works in every browser, one QR scan | once at issuance (auto-renews ~30 days before expiry) | ✅ best UX — the Home Assistant pattern for local HTTPS |
| Built-in local CA + code A install (built in, offline mode) | iOS: install profile + trust toggle (once). Android: Firefox or fallback | never | ✅ keep for fully offline classrooms |
| Native-camera fallback (upload button) | none, but no live viewfinder | never | ✅ always available, automatic |
| `chrome://flags` unsafely-treat-origin-as-secure | per-device flag fiddling | never | ❌ worse than a certificate |
| ngrok / cloud tunnels | none | always on, traffic leaves the LAN | ❌ violates the no-cloud posture |
| USB port-forward to `localhost` | cable + dev tools | never | ❌ not classroom-scale |

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
nothing is reachable from outside, and the classroom traffic itself never
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
   code disappears because students don't need it.

If anything is wrong, the wizard stops at the failing step with a plain-language
fix — e.g. *“myclass.duckdns.org points at 84.x.x.x, but this PC is
192.168.0.15 — open duckdns.org, set the IP to 192.168.0.15, press Start
again”*. Nothing to interpret, nothing to restart.

**Verify it worked:** open the QR-B URL on any phone (or the teacher PC) —
the padlock is clean with no warnings and the scanner shows the
“🔒 Secure camera” chip. If anything fails, the log names the step (bad token,
unreachable duckdns.org, propagation timeout) and the system simply keeps
running the Local-CA HTTPS + HTTP fallbacks — nothing breaks.

**Security notes:** the DuckDNS token is stored in plain text in
`settings.json` (it can only update *your* subdomain's IP/TXT records — keep
the file private anyway); the certificate key lives in `<data>/certs/`;
and students' phones never need the token or any configuration.

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

The Flatpak is self-contained by construction (the manifest pip-installs the
engine into the sandbox at build time). Notes:

- the frozen engine's first launch takes a few extra seconds (one-file
  extraction); subsequent requests are normal speed;
- keep `excludes` in the spec current when you add heavy dev dependencies;
- PyOxidizer was considered and rejected (unmaintained, no current-Python
  support); a full Rust port would shrink the binary but means rewriting a
  tested engine — the frozen route keeps one codebase.

## 5 · Releasing via GitHub Actions

The repo ships **one workflow**, `.github/workflows/main.yml`, that does both
CI and releases:

| Trigger | What runs | Duration |
|---|---|---|
| every push / PR | `selftest` job only — installs deps, runs `python selftest.py` | ~1 min |
| **tag `v*`** (e.g. `v1.0.0`) | selftest **+ all installers below**, attached to a draft GitHub Release | 10–25 min |
| *Actions → Build & Release → Run workflow* | same as a tag (manual test build) | 10–25 min |

**Artifacts per release:**

| Runner | Files you get |
|---|---|
| `ubuntu-22.04` | `.AppImage` · `.deb` · `.rpm` |
| `ubuntu-latest` (container) | `OPTIBubble_vX.Y.Z_x86_64.flatpak` |
| `windows-latest` | `.msi` · NSIS `-setup.exe` |
| `macos-latest` ×2 | `.aarch64.dmg` (M-series) · `.x64.dmg` (Intel) |

**Cutting a release — the exact steps:**

```bash
# 1 · bump the version in THREE files (keep them in sync):
#      optibubble/__init__.py        → __version__ = "1.1.0"
#      src-tauri/tauri.conf.json     → "version": "1.1.0"
#      src-tauri/Cargo.toml          → version = "1.1.0"
#    then refresh the lockfile:
cd src-tauri && cargo update -p optibubble && cd ..

# 2 · commit and tag
git add -A
git commit -m "release: v1.1.0"
git tag v1.1.0
git push origin main --tags
```

3. Watch the build at **Actions → Build & Release** (green ✓ per platform).
4. Open **Releases** → the draft **“OPTIBubble v1.1.0”** now has every
   installer attached. Edit the notes if you like, then press **Publish**.

> The release is created as a *draft* on purpose — nothing is public until you
> publish it. No secrets or signing keys are required for unsigned builds.
> To sign later: Windows → `TAURI_SIGNING_PRIVATE_KEY` secrets (Tauri docs);
> macOS notarization → `APPLE_CERTIFICATE`/`APPLE_ID` secrets; Flathub signs
> Flatpaks for you.

## 6 · The complete `main.yml` (verbatim)

This is the exact file at `.github/workflows/main.yml` in the repo:

```yaml
# ============================================================================
# OPTIBubble — main.yml
# One workflow: CI on every push/PR, release builds on tags (v*) or manual run.
#
#   push / pull_request  → job "selftest" only (fast, ~1 min)
#   tag v* / dispatch    → selftest + installers for every platform:
#                         Windows MSI+NSIS · macOS dmg (Apple Silicon & Intel)
#                         Linux AppImage + deb + RPM  ·  Flatpak bundle
#
# No secrets required. Release is created as a DRAFT — review and publish at
# github.com/<you>/OPTIBubble/releases (see setup.md → "Cutting a release").
# ============================================================================
name: Build & Release

on:
  push:
    branches: [main]
    tags: ["v*"]
  pull_request:
  workflow_dispatch:

permissions:
  contents: write

jobs:
  # ------------------------------------------------------------------- CI ---
  selftest:
    name: Self-test (63 checks)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install engine dependencies
        run: pip install -r requirements.txt

      - name: Run the end-to-end self-test
        run: python selftest.py

  # ------------------------------------------------ Rust shell compiles? ---
  rust-check:
    name: Rust shell (cargo check)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - name: Linux system dependencies (WebKit)
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libayatana-appindicator3-dev \
            librsvg2-dev libxdo-dev libssl-dev build-essential curl wget file pkg-config
      - name: cargo check (src-tauri)
        run: cargo check --manifest-path src-tauri/Cargo.toml

  # ------------------------------------------------- release: native shells -
  tauri:
    name: ${{ matrix.platform }} installers
    needs: selftest
    if: startsWith(github.ref, 'refs/tags/v') || github.event_name == 'workflow_dispatch'
    strategy:
      fail-fast: false
      matrix:
        include:
          # Linux: AppImage + deb + RPM from one build
          - platform: ubuntu-22.04
            args: ""
          # macOS: Apple Silicon + Intel
          - platform: macos-latest
            args: "--target aarch64-apple-darwin"
          - platform: macos-latest
            args: "--target x86_64-apple-darwin"
          # Windows: MSI + NSIS setup
          - platform: windows-latest
            args: ""
    runs-on: ${{ matrix.platform }}
    steps:
      - uses: actions/checkout@v4

      - name: Install Rust (stable)
        uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.platform == 'macos-latest' && 'aarch64-apple-darwin,x86_64-apple-darwin' || '' }}

      - name: Linux system dependencies (WebKit)
        if: matrix.platform == 'ubuntu-22.04'
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libayatana-appindicator3-dev \
            librsvg2-dev libxdo-dev libssl-dev build-essential curl wget file

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Freeze the Python engine (single self-contained binary)
        run: |
          pip install -r requirements.txt pyinstaller
          pyinstaller optibubble.spec --distpath src-tauri/engine \
            --workpath build-engine --noconfirm

      - name: Build bundles & attach to the draft release
        uses: tauri-apps/tauri-action@v0
        with:
          projectPath: .
          tagName: v__VERSION__
          releaseName: "OPTIBubble v__VERSION__"
          releaseBody: "Installers for Windows, macOS and Linux (AppImage/deb/RPM). The Flatpak bundle is attached by the flatpak job. Note: the Python engine (pip install -r requirements.txt) is still required on the target machine — see setup.md."
          releaseDraft: true
          prerelease: false
          args: ${{ matrix.args }}

  # ----------------------------------------------------- release: Flatpak ---
  flatpak:
    name: Flatpak bundle
    needs: selftest
    if: startsWith(github.ref, 'refs/tags/v') || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    container:
      image: bilelmoussaoui/flatpak-github-actions:freedesktop-24.08
      options: --privileged
    steps:
      - uses: actions/checkout@v4

      - name: Build Flatpak
        uses: bilelmoussaoui/flatpak-github-actions/flatpak-builder@v7
        with:
          bundle: OPTIBubble_${{ github.ref_name || 'dev' }}_x86_64.flatpak
          manifest-path: packaging/flatpak/com.optibubble.app.yml
          cache-key: flatpak-builder-${{ github.sha }}

      - name: Attach bundle to the release (tags only)
        if: startsWith(github.ref, 'refs/tags/v')
        uses: softprops/action-gh-release@v2
        with:
          draft: true
          files: OPTIBubble_*_x86_64.flatpak
```

## 7 · Flatpak & Flathub details

The manifest at `packaging/flatpak/com.optibubble.app.yml` packages the
**Python app directly** (no Tauri required) on the Freedesktop 24.08 runtime:
`pip install` of `requirements.txt` into `/app`, the `optibubble/` package
with bundled fonts, a launcher wrapper (`optibubble.sh`) that keeps data
inside the sandbox home, plus the desktop file, icons and AppStream metainfo.

**Publishing to Flathub** (optional, gives automatic distribution + updates):

1. Fork [flathub/flathub](https://github.com/flathub/flathub).
2. Copy `packaging/flatpak/com.optibubble.app.yml` into `apps/` and change the
   `dir` source to a **tagged tarball URL** (Flathub builds must not reference
   mutable branches):
   ```yaml
   sources:
     - type: archive
       url: https://github.com/<you>/OPTIBubble/archive/refs/tags/v1.0.0.tar.gz
       sha256: <sha256sum of the tarball>
   ```
3. Update `com.optibubble.app.metainfo.xml` homepage/bugtracker URLs and add
   a `<release>` entry per version.
4. Open the PR — Flathub reviewers will validate the build; once accepted,
   every new tagged release is picked up automatically.

## 8 · Version bumping checklist

- [ ] `optibubble/__init__.py` → `__version__`
- [ ] `src-tauri/tauri.conf.json` → `version`
- [ ] `src-tauri/Cargo.toml` → `version` (+ `cargo update -p optibubble`)
- [ ] new `<release>` entry in `packaging/flatpak/com.optibubble.app.metainfo.xml`
- [ ] commit → `git tag vX.Y.Z` → `git push --tags` → publish the draft release

## 9 · Troubleshooting

| Symptom | Fix |
|---|---|
| `cargo tauri` not found | `cargo install tauri-cli --version "^2"`; ensure `~/.cargo/bin` is on `PATH` |
| Linux: `webkit2gtk-4.1 not found` | install the §4.3 packages (CI runners already do) |
| Actions release has no artifacts | check the *Actions* log — the release jobs only run on `v*` tags or manual dispatch |
| Flatpak job fails | it needs the privileged container (already configured); try deleting the cache key and re-running |
| Tauri window opens to an error page | the Python engine failed to start — run `python main.py` once to see why |
| Port 5000 busy (macOS) | AirPlay Receiver uses 5000 — `python main.py --port 5050` (HTTPS bridge: `https_port` in Settings) |
| Phone still warns after certificate install | Android Chrome ignores user CAs — use Firefox, or the 🖼️ upload fallback; also check the IP selector matches the phone's network |
| HTTPS bridge not starting | port 5443 busy or `cryptography` missing → see the log card; the HTTP scanner + native-camera fallback keep working |
| Self-test fails locally | reinstall deps (`pip install -r requirements.txt`) — OpenCV/numpy version mismatch is the usual cause |

---

**Next:** [`README.md`](README.md) — features, usage, the OMR engine and the
Regmark design language.
