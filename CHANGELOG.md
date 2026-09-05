# Changelog

All notable changes to **OPTIBubble** are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [2.0.0] — 2026-09-04

### Added
- **Three-pass anchor detection** in the OMR engine — sharp Otsu, then an
  adaptive Gaussian threshold + morphological close that reconnects anchor
  squares split by glare or a hard shadow, then relaxed filters for folded or
  low-contrast corners. Clean photos still pass through the first pass untouched.
- **Stroke-coverage auto-resolution** — a mark that reads light (a light pen /
  soft pencil that still fills the bubble) but is a solid, clearly-winning
  connected stroke is now auto-graded instead of being sent for review. Only
  genuinely ambiguous bubbles (partial strips, smudges, double marks, blanks)
  reach the human review queue.
- **Settings → OMR engine guide** — every slider now carries a plain-English
  hint, plus **one-tap threshold presets** (Ballpoint / Pencil / Low light /
  Soft pencil).
- **Settings → “How bubble checking works”** panel — explains the BLANK / FAINT
  / MULTI flags and the exact auto-accept rule.
- **Mobile scanner: flash (torch) toggle** — uses the camera's real LED where
  exposed, with a graceful fallback message where not.
- **Mobile scanner: rear / front camera switch** with a live `rear`/`user` badge.
- **Mobile scanner: glare/shadow-adaptive anchor thresholds** and a
  **shape-validity gate** so the viewfinder brackets stay sticky and never snap
  onto a mistaken corner.
- **Well-defined mobile scanner states** — distinct, actionable views for camera
  permission denied, no camera, camera in use, upload/network failure, OMR reject
  (with the reason), review (human check) and graded, each with retry / photo
  fallback.
- **README “Download & install” section** describing where to get per-OS
  installers and how to verify them.

### Fixed
- Tauri bundle `identifier` no longer ends with `.app`, which conflicted with the
  macOS application-bundle extension and could break macOS releases.

### Changed
- Version synced to `2.0.0` across `optibubble/__init__.py`,
  `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`, `src-tauri/Cargo.lock`
  and `frontend/package.json`.
- Removed obsolete one-off dev / screenshot / demo-seed scripts
  (`shot_*.py`, `seed_*.py`, `audit_*.py`).
- Build artifacts (`src-tauri/engine/`, `build-engine/`, `optibubble/web/dist/`)
  are now git-ignored; CI rebuilds them on every run.

---

## [1.9.1] — earlier
- WebRTC mirror made deterministic end-to-end; busy-port startup fix; a
  system-wide banner when the engine is unreachable; layout audit clean.
