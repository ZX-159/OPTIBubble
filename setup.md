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
python selftest.py                 # expect: 29/29 checks passed · ALL GREEN
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
    name: Self-test (29 checks)
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

      - name: Build bundles & attach to the draft release
        uses: tauri-apps/tauri-action@v0
        with:
          projectPath: .
          tagName: v__VERSION__
          releaseName: "OPTIBubble v__VERSION__"
          releaseBody: "Installers for Windows, macOS and Linux (AppImage/deb/RPM) plus a Flatpak bundle. The Python engine (pip install -r requirements.txt) is still required — see setup.md."
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
| Port 5000 busy (macOS) | AirPlay Receiver uses 5000 — `python main.py --port 5050` |
| Self-test fails locally | reinstall deps (`pip install -r requirements.txt`) — OpenCV/numpy version mismatch is the usual cause |

---

**Next:** [`README.md`](README.md) — features, usage, the OMR engine and the
Regmark design language.
