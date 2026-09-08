/* OPTIBubble icon set — 24px stroke icons, currentColor (no emoji).
   Style: 1.7px round strokes, Lucide-inspired geometry, hand-tuned. */
"use strict";
const ICONS = {
  home: '<path d="M3 9.5 12 3l9 6.5V20a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 20Z"/><path d="M9 21.5v-7h6v7"/>',
  pencil: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/>',
  scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/>',
  queue: '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
  table: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18"/><path d="M9 10v10"/>',
  settings: '<path d="M4 21v-6"/><path d="M4 9V3"/><path d="M12 21v-9"/><path d="M12 6V3"/><path d="M20 21v-4"/><path d="M20 11V3"/><path d="M2 15h4"/><path d="M10 6h4"/><path d="M18 17h4"/>',
  help: '<circle cx="12" cy="12" r="9.5"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2.6-3 4.5"/><path d="M12 17.5h.01"/>',
  plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  folder: '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2.2 3H20a2 2 0 0 1 2 2Z"/>',
  refresh: '<path d="M21 4v6h-6"/><path d="M3 20v-6h6"/><path d="M4.6 10a8.5 8.5 0 0 1 14-3.2L21 10"/><path d="m3 14 2.4 3.2A8.5 8.5 0 0 0 19.4 14"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9.5"/><path d="M12 16v-4.5"/><path d="M12 8h.01"/>',
  lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  server: '<rect x="2" y="2.5" width="20" height="7.5" rx="2"/><rect x="2" y="14" width="20" height="7.5" rx="2"/><path d="M6 6.2h.01"/><path d="M6 17.8h.01"/>',
  key: '<path d="m21 2-2 2"/><path d="m11.4 11.4 3.1 3.1"/><path d="M13.2 9.6 15.5 7.3l3 3L21 8l-2.5-2.5"/><circle cx="7.5" cy="16.5" r="4.5"/><path d="m10.8 13.2 2.4 2.4"/>',
  shield: '<path d="M20 12.5c0 5-3.6 7.6-7.7 9a1 1 0 0 1-.6 0C7.6 20.1 4 17.5 4 12.5V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1Z"/><path d="m9 12 2 2 4-4"/>',
  globe: '<circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19"/><path d="M12 2.5a14 14 0 0 1 3.8 9.5A14 14 0 0 1 12 21.5a14 14 0 0 1-3.8-9.5A14 14 0 0 1 12 2.5Z"/>',
  camera: '<path d="M14.5 4h-5L7.3 6.8H4a2 2 0 0 0-2 2V18a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8.8a2 2 0 0 0-2-2h-3.3Z"/><circle cx="12" cy="13" r="3.2"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2.5"/><circle cx="9" cy="9" r="1.8"/><path d="m21 15.5-3.4-3.4a2 2 0 0 0-2.8 0L6 21"/>',
  torch: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.4-.5-2-1-3-1.1-2.1-.2-4.1 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.2.4-2.3 1-3a2.5 2.5 0 0 0 2.5 2.5Z"/>',
  arrow: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  printer: '<path d="M6.5 8.5V2.5h11v6"/><path d="M6.5 17.5H4a2 2 0 0 1-2-2V10a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5.5a2 2 0 0 1-2 2h-2.5"/><rect x="6.5" y="14.5" width="11" height="7"/>',
  eye: '<path d="M2.5 12S5.6 5.5 12 5.5 21.5 12 21.5 12 18.4 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>',
  clock: '<circle cx="12" cy="12" r="9.5"/><path d="M12 6.5V12l3.8 2.2"/>',
  qr: '<rect x="3" y="3" width="7.5" height="7.5" rx="1.2"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.2"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.2"/><path d="M13.5 13.5h3v3h-3z"/><path d="M20.2 13.5h.01"/><path d="M20.2 20.2h.01"/><path d="M16.8 20.2h.01"/><path d="M13.5 20.2h.01"/>',
  send: '<path d="m21.5 2.5-7 19-3.8-8.2-8.2-3.8Z"/><path d="M21.5 2.5 10.7 13.3"/>',
  users: '<path d="M16 21v-1.8a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4V21"/><circle cx="9" cy="7.5" r="3.8"/><path d="M22 21v-1.8a4 4 0 0 0-3-3.8"/><path d="M16.5 4a3.8 3.8 0 0 1 0 7.3"/>',
  file: '<path d="M14 2.5H6.5a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V8Z"/><path d="M14 2.5V8h5.5"/><path d="M9 13.5h6"/><path d="M9 17h6"/>',
  zap: '<path d="M13 2 3.5 13.5H11l-1 8.5L19.5 10.5H13l1-8.5Z"/>',
  chevron: '<path d="m9 18 6-6-6-6"/>',
};

function icon(name, size = 16, cls = "") {
  return `<svg class="icsvg ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="1.7"
    stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${
      ICONS[name] || ICONS.info}</svg>`;
}

function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    if (!el.dataset.done) {
      el.innerHTML = icon(el.dataset.icon, el.dataset.size || 16);
      el.dataset.done = "1";
    }
  });
}
