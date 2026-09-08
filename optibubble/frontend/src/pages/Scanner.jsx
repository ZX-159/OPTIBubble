import React, { useEffect, useRef, useState } from "react";
import { AnimatePresence, useReducedMotion, motion } from "motion/react";
import { AlertTriangle, Camera, CameraOff, Check, Flashlight,
         Image as ImageIcon, Moon, RefreshCw, Sun, SwitchCamera, User } from "lucide-react";
import { EdgeOverlay } from "../lib/edge";

/* Map a getUserMedia error to a clear, actionable message.  Keeps the camera
   failure states distinct so the user knows whether to grant permission, close
   another app, or use the photo fallback. */
function camError(err) {
  const n = err?.name || "";
  if (n === "NotAllowedError" || n === "PermissionDeniedError" || n === "SecurityError")
    return { code: "CAM_DENIED",
             msg: "Camera permission was blocked",
             hint: "Allow camera access in your browser settings, or upload a photo instead." };
  if (n === "NotFoundError" || n === "OverconstrainedError" || n === "DevicesNotFoundError")
    return { code: "CAM_NONE",
             msg: "No camera was found",
             hint: "Check the camera works in another app, or upload a photo instead." };
  if (n === "NotReadableError" || n === "TrackStartError" || n === "AbortError")
    return { code: "CAM_BUSY",
             msg: "The camera is busy",
             hint: "Close other apps using the camera, then press Try again." };
  return { code: "CAM_ERROR", msg: "Could not start the camera",
           hint: "Try again, or upload a photo instead." };
}

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* Live mobile scanner — served at /scan/<token>. Vanilla-free React build,
   identical behaviour to the classic page: viewfinder + anchor-lock overlay +
   quick check + upload + result, plus mirror-to-desktop over WebRTC. */
export default function Scanner() {
  const token = window.location.pathname.split("/").pop();
  const reduced = useReducedMotion();
  const [night, setNight] = useState(() => {
    const saved = localStorage.getItem("ob_theme");
    if (saved) return saved === "ink";
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  });
  useEffect(() => {
    document.documentElement.className = night ? "theme-ink" : "theme-day";
    localStorage.setItem("ob_theme", night ? "ink" : "day");
    return () => { document.documentElement.className = "theme-day"; };
  }, [night]);
  const [cfg, setCfg] = useState({ title: "", sub: "", quality: 0.92, width: 2048 });
  const [view, setView] = useState("intro"); // intro|camera|confirm|upload|result
  const [info, setInfo] = useState(null);
  const [blob, setBlob] = useState(null);
  const [warn, setWarn] = useState([]);
  const [res, setRes] = useState(null);
  const [mirrorOn, setMirrorOn] = useState(false);
  const [align, setAlign] = useState(null);
  const [hint, setHint] = useState(null);
  const [qual, setQual] = useState(null);
  const [count, setCount] = useState(+(localStorage.getItem("ob_" + token) || 0));
  const [progress, setProgress] = useState(0);
  const [facing, setFacing] = useState("environment");   // environment|user
  const [torch, setTorch] = useState(false);
  const [camErr, setCamErr] = useState(null);            // {code,msg,hint}
  const [streamId, setStreamId] = useState(0);           // bump to re-attach stream
  const videoRef = useRef(null), canvasRef = useRef(null), streamRef = useRef(null);
  const edgeRef = useRef(null), pcRef = useRef(null), flashRef = useRef(null);
  const mirrorTimerRef = useRef(null);

  useEffect(() => {
    fetch(`/api/info/${token}`).then((r) => r.json()).then((d) => {
      if (d.title) setCfg((c) => ({
        ...c, title: d.title,
        sub: `${d.subject ? d.subject + " · " : ""}${d.questions} questions · ${d.options} options`,
        quality: (d.quality || 92) / 100, width: d.width || 2048 }));
    }).catch(() => {});
    return () => { streamRef.current?.getTracks().forEach((t) => t.stop()); };
  }, [token]);

  const snap = () => {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const c = document.createElement("canvas");
    const scale = Math.min(1, cfg.width / Math.max(v.videoWidth, v.videoHeight));
    c.width = Math.round(v.videoWidth * scale);
    c.height = Math.round(v.videoHeight * scale);
    c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
    c.toBlob((b) => { if (b) { setBlob(b); setView("confirm"); } },
      "image/jpeg", cfg.quality);
  };

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    if (edgeRef.current) { try { edgeRef.current.stop?.(); } catch {} edgeRef.current = null; }
    setTorch(false);
  };

  // (Re)acquire the camera for a given facingMode.  On a clean error it records
  // a distinct, actionable CAM_* state instead of silently falling back, so the
  // user is told exactly what to fix.
  const startCamera = async (facingMode = facing) => {
    setCamErr(null);
    if (streamRef.current) stopStream();       // switch camera / retry
    try {
      const s = window.__OB_TEST_CAM__         // test hook (synthetic stream)
        ? window.__OB_TEST_CAM__
        : await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: facingMode },
                     width: { ideal: cfg.width } }, audio: false });
      streamRef.current = s;
      setFacing(facingMode);
      setStreamId((i) => i + 1);               // re-runs the attach effect
      setView("camera");                       // mounts <video>, effect attaches
      setTimeout(() => {
        if (!streamRef.current) return;        // switched again meanwhile
        edgeRef.current = new EdgeOverlay(videoRef.current, canvasRef.current, {
          onAlign: (m, t) => setAlign({ m, t }),
          onQuality: setQual,
          onAutoCapture: () => {
            flashRef.current?.classList.add("go");
            setTimeout(() => flashRef.current?.classList.remove("go"), 340);
            snap();
          },
        });
        edgeRef.current.autoCapWanted =
          () => localStorage.getItem("ob_autocap") === "1";
        edgeRef.current.start();
        window.__edge = edgeRef.current;       // debug/test handle
      }, 400);
    } catch (err) {
      setCamErr(camError(err));
    }
  };

  const switchCam = async () => {
    const next = facing === "environment" ? "user" : "environment";
    setView("camera");
    await startCamera(next);
  };

  // Real camera torch (LED) where the browser exposes it — the way to actually
  // light the paper so both the snap and the mirrored stream read well.  Where
  // the camera has no torch, tell the user instead of pretending (a CSS overlay
  // wouldn't reach the camera sensor we're streaming).
  const toggleTorch = async () => {
    const track = streamRef.current?.getVideoTracks()[0];
    const caps = track?.getCapabilities?.();
    if (track && caps && caps.torch) {
      try {
        await track.applyConstraints({ advanced: [{ torch: !torch }] });
        setTorch(!torch);
        return;
      } catch {}
    }
    setHint("Torch isn't available on this camera — switch on your phone's flashlight");
  };

  const quickCheck = (b) => new Promise((done) => {
    const img = new Image();
    img.onload = () => {
      const W = 260, c = document.createElement("canvas");
      const H = Math.round(img.height * W / img.width);
      c.width = W; c.height = H;
      const ctx = c.getContext("2d");
      ctx.drawImage(img, 0, 0, W, H);
      const px = ctx.getImageData(0, 0, W, H).data;
      let lsum = 0, n = 0; const dark = new Uint8Array(W * H);
      for (let i = 0; i < px.length; i += 4) {
        const l = .299 * px[i] + .587 * px[i + 1] + .114 * px[i + 2];
        lsum += l; n++; if (l < 85) dark[i / 4] = 1;
      }
      const mean = lsum / n, w = [];
      if (mean < 42) w.push("Very dark photo — turn on more light.");
      else if (mean > 238) w.push("Overexposed — reduce direct light/glare.");
      let corners = 0;
      const gx0 = Math.round(W * .06), gy0 = Math.round(H * .06),
            gw = Math.round(W * .88), gh = Math.round(H * .88),
            bw = Math.round(W * .14), bh = Math.round(H * .11);
      [[gx0, gy0], [gx0 + gw - bw, gy0], [gx0, gy0 + gh - bh],
       [gx0 + gw - bw, gy0 + gh - bh]].forEach(([zx, zy]) => {
        let cnt = 0, tot = 0;
        for (let y = zy; y < zy + bh; y++) for (let x = zx; x < zx + bw; x++) {
          tot++; cnt += dark[y * W + x]; }
        if (cnt / Math.max(1, tot) > .02) corners++;
      });
      if (corners < 3) w.push("Not all 4 corner squares visible — fit the whole sheet in frame.");
      let grad = 0, gn = 0;
      for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) {
        const i = (y * W + x) * 4; grad += Math.abs(px[i] - px[i + 4]); gn++; }
      if (grad / gn < 2.2) w.push("Image looks blurry — clean the lens and hold steady.");
      done(w); URL.revokeObjectURL(img.src);
    };
    img.src = URL.createObjectURL(b);
  });

  useEffect(() => {
    if (view !== "confirm" || !blob) return;
    setWarn([]);
    quickCheck(blob).then(setWarn);
  }, [view, blob]);

  // attach the live stream once the <video> mounts.  With AnimatePresence
  // mode="wait" the video mounts AFTER the intro's exit animation, so a
  // single effect pass can race — retry until frames actually flow.
  useEffect(() => {
    if (view !== "camera" || !streamRef.current) return;
    let tries = 0;
    const iv = setInterval(() => {
      const v = videoRef.current, s = streamRef.current;
      if (v && s) {
        if (v.srcObject !== s) v.srcObject = s;
        v.play().catch(() => {});
      }
      if ((v && v.videoWidth > 0) || ++tries > 50) clearInterval(iv);
    }, 100);
    return () => clearInterval(iv);
  }, [view, streamId]);

  const send = () => {
    setView("upload");
    const fd = new FormData();
    fd.append("photo", blob, "sheet.jpg");
    const x = new XMLHttpRequest();
    x.open("POST", `/api/upload/${token}`);
    x.upload.onprogress = (e) => {
      if (e.lengthComputable) setProgress(10 + 80 * e.loaded / e.total);
    };
    x.onload = () => {
      if (x.status !== 200) return fail("NETWORK", "Upload failed (" + x.status + ").",
        "Check the Wi-Fi connection and try again.");
      try { poll(JSON.parse(x.responseText).receipt); } catch {
        fail("NETWORK", "Unexpected server reply.", "Try again."); }
    };
    x.onerror = () => fail("NETWORK", "Connection to the desktop was lost.",
      "Make sure both devices are on the same Wi-Fi.");
    x.send(fd);
  };
  const poll = (rid) => {
    setProgress(95);
    const t0 = Date.now();
    (function loop() {
      fetch(`/api/receipt/${rid}`).then((r) => r.json()).then((d) => {
        if (d.status === "done") { setProgress(100); setRes(d.result);
          setCount((c) => { const n = c + 1;
            localStorage.setItem("ob_" + token, n); return n; });
          setTimeout(() => setView("result"), 250); }
        else if (d.status === "error")
          fail(d.error.code, d.error.message, d.error.hint);
        else if (Date.now() - t0 > 25000)
          fail("TIMEOUT", "Grading is taking unusually long.",
            "Finish it from the review queue on the desktop.");
        else setTimeout(loop, 650);
      }).catch(() => {
        if (Date.now() - t0 > 25000)
          fail("TIMEOUT", "Lost contact while grading.", "Try again.");
        else setTimeout(loop, 900);
      });
    })();
  };
  const fail = (code, msg, hint) => setRes({ failed: true, code, msg, hint }) ||
    setView("result");

  const mirror = async () => {
    if (mirrorTimerRef.current) { clearInterval(mirrorTimerRef.current);
      mirrorTimerRef.current = null; }
    if (pcRef.current) {
      try { pcRef.current.close(); } catch {}
      pcRef.current = null; setMirrorOn(false);
      return;
    }
    if (!streamRef.current) {
      setHint("Start the camera first");
      return;
    }
    setHint("Looking for the desktop…");
    try {
      let offer = null;
      for (let i = 0; i < 24 && !offer; i++) {           // ~22 s window
        try {
          const r = await fetch("/api/mirror/offer").then((x) => x.json());
          if (r.payload) {
            offer = r.payload;
            await fetch("/api/mirror/offer", { method: "DELETE" });  // consume
          }
        } catch {}
        if (!offer) await new Promise((r) => setTimeout(r, 900));
      }
      if (!offer) {
        setHint("Desktop isn't monitoring — press “Start monitoring” on it first");
        return;
      }
      const pc = new RTCPeerConnection();
      pcRef.current = pc;
      streamRef.current.getVideoTracks().forEach((t) => pc.addTrack(t, streamRef.current));
      await pc.setRemoteDescription(offer);
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      await new Promise((res) => {
        const t = setTimeout(res, 3000);
        if (pc.iceGatheringState === "complete") { clearTimeout(t); res(); return; }
        pc.addEventListener("icegatheringstatechange", () => {
          if (pc.iceGatheringState === "complete") { clearTimeout(t); res(); }
        }, { once: true });
      });
      if (!pcRef.current) return;                       // toggled off mid-way
      await fetch("/api/mirror/answer", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pc.localDescription),
      });
      const resetMirror = (why) => {
        setMirrorOn(false);
        if (pcRef.current === pc) { try { pc.close(); } catch {} pcRef.current = null; }
        setHint(why);
      };
      pc.oniceconnectionstatechange = () => {
        const st = pc.iceConnectionState;
        if (st === "failed") resetMirror("Mirror failed — tap ⌁ to retry");
        else if (st === "disconnected") resetMirror("Desktop stopped the mirror");
      };
      pc.onconnectionstatechange = () => {
        const st = pc.connectionState;
        if (st === "failed") resetMirror("Mirror failed — tap ⌁ to retry");
        else if (st === "disconnected" || st === "closed")
          resetMirror("Desktop stopped the mirror");
      };
      setMirrorOn(true);
      setHint("Mirroring to the desktop · tap ⌁ again to stop");
      // deterministic teardown watch: ICE events can lag when the desktop
      // closes without signalling — poll the state while mirroring
      const hangup = (why) => {
        clearInterval(mirrorTimerRef.current); mirrorTimerRef.current = null;
        if (pcRef.current === pc) {
          try { pc.close(); } catch {}
          pcRef.current = null;
        }
        setMirrorOn(false);
        setHint(why);
      };
      mirrorTimerRef.current = setInterval(async () => {
        const st = pc.connectionState, ist = pc.iceConnectionState;
        if (st === "failed" || st === "disconnected" || st === "closed" ||
            ist === "failed" || ist === "disconnected" || ist === "closed") {
          hangup("Desktop stopped the mirror");
          return;
        }
        try {                       // explicit bye from the desktop
          const r = await fetch("/api/mirror/bye").then((x) => x.json());
          if (r.payload) hangup("Desktop stopped the mirror");
        } catch {}
      }, 1200);
    } catch {
      if (pcRef.current) { try { pcRef.current.close(); } catch {} pcRef.current = null; }
      setMirrorOn(false);
      setHint("Mirror failed — check both devices share the Wi-Fi");
    }
  };
  useEffect(() => () => {                 // leave page → close cleanly
    if (mirrorTimerRef.current) clearInterval(mirrorTimerRef.current);
    if (pcRef.current) { try { pcRef.current.close(); } catch {} pcRef.current = null; }
  }, []);

  const btn = "inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 " +
    "text-[14px] font-extrabold";
  const secBtn = `${btn} border border-hair2 bg-fill text-ink2`;
  return (
    <div className="mx-auto flex min-h-dvh max-w-[560px] flex-col">
      <header className="sticky top-0 z-20 flex items-center gap-2.5 border-b
        border-hair bg-[color-mix(in_srgb,var(--bg1)_88%,transparent)] px-4 py-3
        backdrop-blur">
        <span className="regmark regmark-iris shrink-0" aria-hidden="true" />
        <span className="fbrand shrink-0 text-[19px] leading-none" style={{ color: "var(--tx)" }}>
          OPTIBubble</span>
        <div className="ml-auto flex items-center gap-2">
          <span className={`rounded-full px-2.5 py-1 text-[9.5px] font-extrabold
            uppercase tracking-[.1em] ${window.isSecureContext
              ? "bg-okdim text-ok" : "bg-fill text-ink3"}`}>
            {window.isSecureContext ? "secure camera" : "connected"}</span>
          <button onClick={() => setNight((n) => !n)} aria-label="Toggle theme"
            className="focusable hov flex h-8 w-8 shrink-0 items-center justify-center
              rounded text-ink2">{night ? <Sun size={15} /> : <Moon size={15} />}</button>
        </div>
      </header>

      <main className="flex flex-1 flex-col items-center px-4 py-4">
        <AnimatePresence mode="wait">
          {view === "intro" && (
            <motion.section key="intro" initial={reduced ? false : { opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
              transition={reduced ? { duration: 0.1 } : { type: "spring", stiffness: 380, damping: 30 }}
              className="my-auto w-full rounded-card border border-hair bg-surface p-5
                text-center shadow-card">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-branddim
                px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-[.1em]
                text-brandhi"><Camera size={12}/> Scan with your phone</span>
              <h1 className="mt-3 text-[18px] font-extrabold leading-snug text-ink">
                {cfg.title || "Loading test…"}</h1>
              <p className="mt-1 mb-4 text-[12.5px] text-ink3">{cfg.sub || "—"}</p>
              <ol className="mx-auto mb-5 max-w-[300px] list-disc space-y-2.5 pl-5
                text-left text-[13px] leading-relaxed text-ink2">
                <li>Hold the sheet <b className="text-ink">flat</b> and well-lit</li>
                <li>Fit all <b className="text-ink">4 corner squares</b> in frame</li>
                <li>Snap — it grades in milliseconds</li>
              </ol>
              <div className="flex flex-col gap-2.5">
                <button onClick={startCamera}
                  className={`${btn} w-full bg-brand text-brandink shadow-brand`}>
                  <Camera size={16}/> Start camera</button>
                <button onClick={() => $("fileInput").click()}
                  className={`${secBtn} w-full`}>
                  <ImageIcon size={15}/> Upload a photo instead</button>
              </div>
              <label className="mt-3.5 flex cursor-pointer items-center justify-center
                gap-2 py-1 text-[12.5px] text-ink2">
                <input type="checkbox" defaultChecked={
                  localStorage.getItem("ob_autocap") === "1"}
                  onChange={(e) => localStorage.setItem("ob_autocap",
                    e.target.checked ? "1" : "0")}
                  className="h-3.5 w-3.5 accent-[var(--brand)]"/>
                Auto-capture when aligned</label>
            </motion.section>
          )}

          {view === "camera" && (
            <motion.section key="cam" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="w-full">
              {camErr ? (
                <div className="aspect-[3/4] max-h-[62vh] w-full overflow-hidden
                  rounded-card border border-hair bg-surface p-6 text-center
                  flex flex-col items-center justify-center">
                  <span className="inline-flex items-center gap-1.5 rounded-full
                    bg-errdim px-2.5 py-1 text-[10px] font-extrabold uppercase
                    tracking-[.1em] text-err"><CameraOff size={12}/>{camErr.code}</span>
                  <h1 className="mt-3 text-[15px] font-extrabold text-ink">{camErr.msg}</h1>
                  <p className="mt-1 max-w-[280px] text-[12px] leading-relaxed text-ink3">
                    {camErr.hint}</p>
                  <div className="mt-4 flex flex-col gap-2">
                    <button onClick={() => startCamera()}
                      className={`${btn} w-full bg-brand text-brandink shadow-brand`}>
                      <RefreshCw size={15}/> Try again</button>
                    <button onClick={() => $("fileInput").click()}
                      className={`${secBtn} w-full`}>
                      <ImageIcon size={15}/> Take a photo instead</button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="reticle relative aspect-[3/4] max-h-[62vh] w-full
                    overflow-hidden rounded-card border border-hair bg-surface">
                    <video ref={videoRef} autoPlay playsInline muted
                      className="h-full w-full object-cover"/>
                    <canvas ref={canvasRef}
                      className="pointer-events-none absolute inset-0 h-full w-full"/>
                    <div ref={flashRef}
                      className="pointer-events-none absolute inset-0 bg-white opacity-0"/>
                    <div className="pointer-events-none absolute inset-x-0 top-0 flex
                      justify-center pt-2.5">
                      <span className={`rounded-full px-2.5 py-1 text-[9.5px]
                        font-extrabold uppercase tracking-[.14em] ${facing === "user"
                          ? "bg-fill text-ink3" : "bg-okdim text-ok"}`
                      }>rear</span>
                    </div>
                    <div className="pointer-events-none absolute inset-x-0 bottom-0
                      bg-gradient-to-t from-black/85 to-transparent px-3.5 pb-3 pt-8
                      text-center text-[11.5px] text-white">
                      {hint || (align
                        ? (align.m === "ok"
                          ? <b className="text-[var(--brand)]">{align.t}</b>
                          : align.t)
                        : "Fill the frame — all 4 black corner squares must be visible")}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center justify-center gap-2 pt-3">
                    {[
                      [`${qual?.anchors ?? "–"}/4 anchors`,
                       (qual?.anchors ?? 0) === 4 ? "ok" : "warn"],
                      [qual?.exposure === "dark" ? "too dark"
                       : qual?.exposure === "glare" ? "glare" : "exposure ok",
                       qual?.exposure === "ok" || !qual ? "mute" : "warn"],
                      [qual?.focus === "soft" ? "hold steady"
                       : qual?.focus === "noisy" ? "noisy" : "focus ok",
                       qual?.focus === "ok" || !qual ? "mute" : "warn"],
                      ...(qual?.coverage ? [`${qual.coverage}% frame`] : []),
                    ].map(([label, tone]) => (
                      <span key={label} className={`rounded-full px-2.5 py-0.5
                        font-mono text-[9.5px] font-medium uppercase tracking-[.14em]
                        ${tone === "ok" ? "bg-okdim text-ok"
                          : tone === "warn" ? "bg-warndim text-warn"
                          : "bg-fill text-ink3"}`}>{label}</span>
                    ))}
                  </div>
                  <div className="flex items-center justify-center gap-2.5 py-3">
                    <button onClick={switchCam} aria-label="Switch camera"
                      className={`focusable flex h-11 w-11 items-center justify-center
                        rounded ${facing === "user" ? "bg-brand text-brandink"
                          : "bg-fill text-ink2"}`}>
                      <SwitchCamera size={18}/></button>
                    <button onClick={toggleTorch} aria-label="Flash"
                      className={`focusable flex h-11 w-11 items-center justify-center
                        rounded ${torch ? "bg-brand text-brandink" : "bg-fill text-ink2"}`}>
                      <Flashlight size={18}/></button>
                    <button onClick={snap} aria-label="Capture"
                      className="focusable relative h-[68px] w-[68px] rounded-md bg-brand
                        text-brandink active:scale-95">
                      <span className="absolute inset-[7px] rounded-[4px] border-2
                        border-brandink/80"/>
                    </button>
                    <button onClick={() => $("fileInput").click()} aria-label="Gallery"
                      className="focusable flex h-11 w-11 items-center justify-center
                        rounded bg-fill text-ink2"><ImageIcon size={18}/></button>
                    <button onClick={mirror} aria-label="Mirror to desktop"
                      className={`focusable flex h-11 w-11 items-center justify-center
                        rounded text-[18px] ${mirrorOn ? "bg-brand text-brandink"
                          : "bg-fill text-ink2"}`}>⌁</button>
                  </div>
                </>
              )}
            </motion.section>
          )}

          {view === "confirm" && (
            <motion.section key="conf" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="w-full">
              <div className="aspect-[3/4] max-h-[62vh] w-full overflow-hidden
                rounded-card border border-hair bg-surface">
                <img src={URL.createObjectURL(blob)} alt="captured"
                  className="h-full w-full object-cover"/></div>
              {warn.length > 0 && (
                <div className="mt-2.5 rounded bg-warndim px-3 py-2.5 text-[11.5px]
                  leading-relaxed text-warn">
                  <b>Quick check</b><br/>
                  {warn.map((w) => <span key={w}>{"• " + w}<br/></span>)}
                  You can retake, or send anyway — the desktop will verify.</div>)}
              <div className="flex gap-2.5 pt-3.5">
                <button onClick={() => { setBlob(null); setView("camera"); }}
                  className={`${btn} flex-1 border border-hair2 bg-fill`}>Retake</button>
                <button onClick={send}
                  className={`${btn} flex-1 bg-ok text-[#08130C]`}>
                  Send <Check size={15}/></button>
              </div>
            </motion.section>
          )}

          {view === "upload" && (
            <motion.section key="up" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="w-full rounded-card border border-hair bg-surface p-5 text-center">
              <div className="mx-auto mb-3 h-10 w-10 animate-spin rounded-full
                border-[3px] border-hair2 border-t-brand"/>
              <h1 className="text-[15px] font-extrabold">Grading on the desktop…</h1>
              <p className="text-[12px] text-ink3">Perspective correction → bubble
                analysis → scoring</p>
              <div className="mt-3 h-[3px] overflow-hidden rounded bg-fill">
                <div className="h-full bg-brand transition-[width] duration-300"
                  style={{ width: `${progress}%` }}/></div>
            </motion.section>
          )}

          {view === "result" && res && (
            <motion.section key="res" initial={reduced ? false : { opacity: 0, scale: 0.94 }}
              animate={{ opacity: 1, scale: 1 }}
              className="w-full rounded-card border border-hair bg-surface p-5 text-center">
              {res.failed ? (
                <>
                  <span className="inline-flex items-center gap-1.5 rounded-full
                    bg-errdim px-2.5 py-1 text-[10px] font-extrabold uppercase
                    tracking-[.1em] text-err"><AlertTriangle size={12}/>{res.code}</span>
                  <h1 className="mt-2.5 text-[15px] font-extrabold">{res.msg}</h1>
                  <p className="text-[12px] text-ink3">{res.hint}</p>
                </>
              ) : res.status === "auto" ? (
                <>
                  <span className="inline-flex items-center gap-1.5 rounded-full
                    bg-okdim px-2.5 py-1 text-[10px] font-extrabold uppercase
                    tracking-[.1em] text-ok"><Check size={12}/> Graded instantly</span>
                  <p className="mt-2 text-[12px] text-ink3">
                    Student {res.student_id || "—"}</p>
                  <div className="tnum text-[42px] font-extrabold leading-none text-ok">
                    {res.score}
                    <span className="text-[18px] text-ink3">/{res.max}</span></div>
                  <div className="mt-3 flex justify-center gap-7">
                    <div><b className="tnum block text-[19px]">
                      {res.max ? Math.round(100 * res.score / res.max) : 0}%</b>
                      <span className="text-[9px] font-extrabold uppercase tracking-[.12em]
                        text-ink3">score</span></div>
                    <div><b className="tnum block text-[19px]">
                      {Math.round((res.confidence || 0) * 100)}%</b>
                      <span className="text-[9px] font-extrabold uppercase tracking-[.12em]
                        text-ink3">confidence</span></div>
                  </div>
                </>
              ) : (
                <>
                  <span className="inline-flex items-center gap-1.5 rounded-full
                    bg-warndim px-2.5 py-1 text-[10px] font-extrabold uppercase
                    tracking-[.1em] text-warn"><User size={12}/> Sent for review</span>
                  <h1 className="mt-2.5 text-[15px] font-extrabold">
                    Sent for review</h1>
                  <p className="text-[12px] text-ink3">
                    {(res.flags || []).length} item(s) need a human check.</p>
                </>
              )}
              <button onClick={() => { setBlob(null); setRes(null);
                  setView(streamRef.current ? "camera" : "intro"); }}
                className={`${btn} mt-4 w-full bg-brand text-brandink`}>
                Scan next sheet →</button>
            </motion.section>
          )}
        </AnimatePresence>
        <input id="fileInput" type="file" accept="image/*" capture="environment"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (!f) return;
            const img = new Image();
            img.onload = () => {
              const c = document.createElement("canvas");
              const sc = Math.min(1, cfg.width / Math.max(img.width, img.height));
              c.width = Math.round(img.width * sc);
              c.height = Math.round(img.height * sc);
              c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
              c.toBlob((b) => { if (b) { setBlob(b); setView("confirm"); } },
                "image/jpeg", cfg.quality);
              URL.revokeObjectURL(img.src);
            };
            img.src = URL.createObjectURL(f);
          }}/>
      </main>
      <footer className="sticky bottom-0 z-20 border-t border-hair bg-[var(--bg1)]
        px-4 py-2.5">
        <p className="flex items-center justify-center gap-1.5 text-center text-[11px]
          text-ink3">
          <b className="tnum text-ink2">{count}</b> submitted · local network only —
          data never leaves the room</p>
      </footer>
    </div>
  );
}
