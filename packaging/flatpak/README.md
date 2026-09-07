# OPTIBubble — Flatpak packaging

This directory produces the Flathub-style Flatpak bundle
(`com.optibubble.app`). It is built entirely **offline**: everything the sandbox
needs is either provided by the freedesktop runtime/SDK or vendored as a
pre-downloaded source. The `flatpak` job in `.github/workflows/main.yml` does the
build; it requires no signing secrets and uploads a `.flatpak` bundle to the
draft release.

## How the two known Flatpak failure modes are resolved

### 1. `pip install -r requirements.txt` inside the sandbox (network at compile)

Flatpak runs `build-commands` in a sandbox with **no network**. A naive
`pip install -r requirements.txt` therefore fails immediately.

Fix: **vendor the whole dependency closure as wheels.** `tools/flatpak_deps.py`
resolves the exact closure for the freedesktop 24.08 runtime (CPython 3.12,
modern manylinux) and writes `packaging/flatpak/python-deps.yml` — a list of
`type: file` `sources` pointing at the canonical PyPI URLs and SHA-256 digests.
flatpak-builder fetches these during the **source-download** phase (where the
network *is* available) and drops them into `wheels/`; the `python3-deps` module
then installs them with `--no-index`:

```sh
python3 -m pip install --no-index --no-deps --prefix=/app wheels/*.whl
```

No `pip install`/`npm install` happens during the compile. Re-run the generator
after any `requirements.txt` change:

```sh
python3 tools/flatpak_deps.py
```

### 2. PyInstaller `onefile` + immutable OSTree `/app` (`/tmp` / `_MEIPASS`)

The engine's PyInstaller freeze uses `--onefile`, so at launch it unpacks its
bundled data to a temp dir under `sys._MEIPASS`. In a Flatpak sandbox `/app` is a
read-only OSTree mount, and this `/tmp`-extraction path is exactly the kind of
thing that breaks against a sandbox (no `--filesystem` permission, or the app
tries to write next to a read-only location).

Fix: the Flatpak **runs from source** — `python3 main.py` — instead of shipping
a frozen binary. There is no `_MEIPASS` at all, so there is nothing for the
sandbox to refuse. The launcher (`optibubble.sh`) only sets the persistent data
directory (`$XDG_DATA_HOME/OPTIBubbleData`, which the manifest grants via
`--filesystem=xdg-data`) and adds the app-installed packages to `PYTHONPATH`.

> If you ever want the Flatpak to ship the frozen binary instead, switch the
> `command` to the `optibubble-engine` binary, add the PyInstaller output as a
> `sources`/`build-commands` copy, and grant `--filesystem` for the temp + data
> locations the binary writes. Source-run is preferred because it is smaller and
> has no sandbox/runtime pitfalls.

## Files

- `com.optibubble.app.yml` — the manifest. Two modules: `python3-deps`
  (vendored wheels, installed offline) and `optibubble` (the app + desktop
  integration). `type: dir path: ../..` snapshots the repo, restricted by `files`.
- `python-deps.yml` — **generated** `sources:` fragment for `python3-deps`.
  Do not hand-edit.
- `optibubble.sh` — launcher; sets `XDG_DATA_HOME` data dir and `PYTHONPATH`.
- `com.optibubble.app.desktop` / `com.optibubble.app.metainfo.xml` — desktop
  entry + AppStream metadata (general-user narrative).
- `../..` refers to the repo root; the manifest lives in `packaging/flatpak/`.

## Build locally (optional)

```sh
python3 tools/flatpak_deps.py
flatpak-builder --force-clean --user build-dir packaging/flatpak/com.optibubble.app.yml
```

(Requires the freedesktop 24.08 SDK + runtime; the CI uses
`flatpak/flatpak-github-actions`.)
