import React from "react";
import { Card } from "../components/ui";
const FAQ = [
  ["How do I scan sheets?",
   "Start the server on Scan & Serve, then open the QR link with any phone camera. The scanner runs in the browser — no app, no account, no internet. The phone just needs to share this computer's Wi-Fi."],
  ["The phone shows a camera error / black view — why?",
   "Browsers only allow the in-page camera on HTTPS. The zero-setup fix is Trusted HTTPS mode (Settings → Live camera): a built-in Let's Encrypt client issues a real certificate for your free duckdns.org domain. Offline instead? Users scan code 1 once (Android: use Firefox). Otherwise the scanner falls back to the native camera app — graded exactly the same."],
  ["What pens or pencils work best?",
   "Black or dark blue ballpoint gives the highest confidence; dark pencils (2B) work too. Fill bubbles completely and erase cleanly — faint or half-erased marks are intentionally flagged for review."],
  ["What gets flagged for review?",
   "Unanswered, double-marked, and marks inside the ambiguity band. Thresholds are tunable in Settings → OMR engine; auto-accept blanks reduces the load."],
  ["A sheet was rejected — what now?",
   "The phone shows the exact reason. Common causes: a corner square hidden, too dark, too blurry, or a very steep angle. Flatten the sheet, avoid shadows, include all four black corner squares."],
  ["Where is my data stored?",
   "Everything stays on this computer (~/OPTIBubbleData). Each test keeps its PDF, photos, crops and results.csv. Nothing is uploaded anywhere."],
  ["Can I print with any printer?",
   "Yes — plain A4 or Letter at 100% scale ('Actual size', not 'Fit to page')."],
  ["How many questions fit on one sheet?",
   "Up to 102 on A4 (1–3 columns), with 2–5 options each."],
  ["Can several phones scan at once?",
   "Yes — the server accepts simultaneous uploads and grades in parallel."],
  ["How do I get results into Excel?",
   "Results → Export CSV. The Detailed_Answers_JSON column holds the full per-question breakdown."],
  ["The QR code doesn't open anything.",
   "Same Wi-Fi? Firewall allows the port? URL matches this PC's IP? Some routers block phone→PC traffic ('AP/client isolation') — disable it."],
  ["Can I run this as a native desktop app?",
   "Yes — the bundled Tauri shell produces installers. See setup.md."],
  ["What is the desktop camera?",
   "Plug any USB document camera into the PC, start it on Scan & Serve, and grade straight at the desk — live preview plus one-click capture."],
  ["What is mirroring?",
   "Tap the mirror button in the camera view and the live viewfinder appears on the desktop over local WebRTC — check framing at a glance."],
];
export default function Help() {
  return (
    <div className="space-y-4">
      <Card title="About OPTIBubble">
        <p className="text-[12.5px] leading-relaxed text-ink2">
          Local computer-vision OMR grading with a mobile-bridge scanner. Sheets
          are generated, photographed on any phone over Wi-Fi and graded with
          OpenCV on this machine. Nothing leaves your network.</p>
      </Card>
      <Card title="FAQ">
        <div className="divide-y divide-hair">
          {FAQ.map(([q, a]) => (
            <details key={q} className="group py-2.5">
              <summary className="flex cursor-pointer list-none items-center gap-2.5
                text-[12.5px] font-bold">
                <span className="text-[15px] font-extrabold text-brand
                  group-open:rotate-45 transition-transform">+</span>{q}</summary>
              <p className="mt-2 pl-7 text-[12px] leading-relaxed text-ink3">{a}</p>
            </details>
          ))}
        </div>
      </Card>
    </div>
  );
}
