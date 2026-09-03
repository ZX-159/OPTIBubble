import React, { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  Camera, Check, Copy, Eye, KeyRound, MonitorUp, Play, Printer, RefreshCw,
  Square, Upload,
} from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../App";
import { Badge, Button, Card, Field, Input, LiveBadge, Select, useToast,
         spring } from "../components/ui";

/* ================= QR + server control ================= */
function QrPanel() {
  const { state, refresh } = useApp();
  const toast = useToast();
  const [ip, setIp] = useState("");
  const [busy, setBusy] = useState(false);
  const s = state?.server || {};
  const ips = (s.ips || []).filter((x) => !x.startsWith("127."));
  useEffect(() => { if (!ip && ips.length) setIp(ips[0]); }, [ips, ip]);
  const trusted = !!(s.https_domain && s.https_running);
  const test = state?.test;
  const scanUrl = !test ? "" : s.https_running
    ? `https://${trusted ? s.https_domain : ip}:${s.https_port}/scan/${test.session_token}`
    : `http://${ip}:${s.port}/scan/${test.session_token}`;
  const certUrl = `http://${ip}:${s.port}/cert`;

  const toggle = async () => {
    setBusy(true);
    try {
      if (s.running) { await api("/api/serve/stop", { method: "POST" }); toast("Server stopped"); }
      else {
        const r = await api("/api/serve/start", { method: "POST" });
        r.ok ? toast("Server started — " + r.url, "ok") : toast("Could not start: " + (r.error || ""), "err");
      }
    } catch (e) { toast(e.message, "err"); }
    await refresh(true); setBusy(false);
  };

  return (
    <Card title="User scan">
      {!test ? <p className="text-[12.5px] text-ink3">Create a test first.</p> : !s.running ? (
        <div className="space-y-3">
          <p className="text-[12.5px] leading-relaxed text-ink2">
            The server is <b>offline</b> — start it to show the scan QR code.</p>
        </div>
      ) : (
        <>
          <p className="mb-3 text-[12px] leading-relaxed text-ink3">
            {trusted
              ? <>Users scan this <b className="text-ink2">once per session</b> — the live
                 camera opens automatically, no install, any phone.</>
              : s.https_running
              ? <>Two steps, <b className="text-ink2">once per phone</b>: scan <b>1</b> to
                 enable the live camera, then scan <b>2</b> every class. In a hurry? Scan 2
                 and use the upload button — it always works.</>
              : <>Users scan and use the upload button (native camera). The live
                 viewfinder needs the HTTPS setup in Settings.</>}
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {s.https_running && !trusted && (
              <div className="flex flex-col items-center gap-1.5 text-center">
                <span className="rounded-full bg-warndim px-2.5 py-0.5 text-[9.5px]
                  font-extrabold uppercase tracking-[.12em] text-warn">Step 1 · once</span>
                <div className="reticle rounded bg-base p-2">
                  <img src={`/api/qr.png?url=${encodeURIComponent(certUrl)}&t=${Date.now()}`}
                    alt="Install certificate" className="h-[150px] w-[150px] bg-white"/></div>
                <b className="text-[12px]">Enable the live camera</b>
                <span className="text-[10.5px] text-ink3">one-time certificate install</span>
              </div>
            )}
            <div className={`flex flex-col items-center gap-1.5 text-center
              ${s.https_running && !trusted ? "" : "sm:col-span-2"}`}>
              <span className="rounded-full bg-okdim px-2.5 py-0.5 text-[9.5px]
                font-extrabold uppercase tracking-[.12em] text-ok">
                {trusted ? "Scan to grade" : "Step 2 · every class"}</span>
              <div className="reticle rounded bg-base p-2">
                <img src={`/api/qr.png?url=${encodeURIComponent(scanUrl)}&t=${Date.now()}`}
                  alt="Open the scanner" className="h-[158px] w-[158px] bg-white"/></div>
              <b className="text-[12px]">{trusted ? "Scan to grade" : "Open the scanner"}</b>
              <span className="text-[10.5px] text-ink3">
                {trusted ? "live camera · trusted HTTPS"
                  : s.https_running ? "live camera (after step 1)" : "native-camera upload"}</span>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <Input readOnly value={scanUrl} className="flex-1 font-mono text-[11px]"/>
            <Button variant="ghost" icon={Copy}
              onClick={() => navigator.clipboard.writeText(scanUrl)
                .then(() => toast("Link copied", "ok"))}>Copy</Button>
          </div>
          {ips.length > 1 && (
            <Select className="mt-2" value={ip} onChange={(e) => setIp(e.target.value)}>
              {ips.map((x) => <option key={x} value={x}>{x}</option>)}
            </Select>
          )}
        </>
      )}
      <div className="mt-4 flex flex-col gap-2">
        {s.running
          ? <Button variant="danger" icon={Square} loading={busy} onClick={toggle}>Stop server</Button>
          : <Button icon={Play} loading={busy} onClick={toggle}>Start server</Button>}
        <div className="flex gap-2">
          <a href="/api/sheet.pdf" target="_blank" rel="noopener"
            className="focusable btn-hov flex flex-1 items-center justify-center gap-2
              rounded border border-hair2 bg-fill px-3 py-2 text-[12px] font-extrabold">
            <Printer size={13}/> Sheet PDF · 100%</a>
          <a href="/api/key.pdf" target="_blank" rel="noopener"
            className="focusable btn-hov flex flex-1 items-center justify-center gap-2
              rounded border border-hair2 bg-fill px-3 py-2 text-[12px] font-extrabold">
            <KeyRound size={13}/> Answer key</a>
        </div>
      </div>
    </Card>
  );
}

/* ================= answer key (editable after print) ================= */
function KeyCard() {
  const { state, refresh } = useApp();
  const toast = useToast();
  const [txt, setTxt] = useState("");
  const [busy, setBusy] = useState(false);
  const t = state?.test;
  useEffect(() => {
    if (t?.answer_key) setTxt(
      Object.entries(t.answer_key).sort((a, b) => a[0] - b[0])
        .map(([q, a]) => `${q}:${a}`).join(" "));
  }, [t?.test_id]);
  if (!t) return null;
  const defined = Object.keys(t.answer_key || {}).length;
  return (
    <Card title="Answer key" right={
      defined >= t.num_questions ? <Badge tone="ok">complete</Badge>
        : <Badge tone="warn">{defined}/{t.num_questions}</Badge>}>
      <p className="-mt-2 mb-3 text-[11.5px] text-ink3">
        {defined >= t.num_questions
          ? "Every question has a key."
          : "Grading scores only defined questions until the key is complete."}</p>
      <div className="flex gap-2">
        <Input value={txt} onChange={(e) => setTxt(e.target.value)}
          placeholder="1:A 2:C … or ABCD…" className="flex-1 font-mono text-[11.5px]"/>
        <Button loading={busy} onClick={async () => {
          setBusy(true);
          try {
            const entries = {};
            (txt.toUpperCase().match(/(\d{1,3})\s*[:.\-]\s*([A-E])/g) || [])
              .forEach((m) => { const g = m.match(/(\d{1,3})\s*[:.\-]\s*([A-E])/);
                                entries[+g[1]] = g[2]; });
            if (!Object.keys(entries).length)
              [...txt.toUpperCase().replace(/[^A-E]/g, "")].forEach(
                (a, i) => { entries[i + 1] = a; });
            const r = await api("/api/key", { method: "POST",
              body: JSON.stringify({ entries, replace: true })});
            toast(`Key updated — ${r.defined}/${r.total} defined`, "ok");
            await refresh(true);
          } catch (e) { toast(e.message, "err"); }
          setBusy(false);
        }}>Save</Button>
      </div>
    </Card>
  );
}

/* ================= desktop USB camera ================= */
function CameraPanel() {
  const { state } = useApp();
  const toast = useToast();
  const [devices, setDevices] = useState([]);
  const [dev, setDev] = useState("0");
  const [live, setLive] = useState(false);
  const [frame, setFrame] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api("/api/camera/devices").then((d) => {
      setDevices(d); if (d.length) setDev(String(d[0].index));
    }).catch(() => {});
  }, []);
  useEffect(() => {
    if (!live) return;
    const iv = setInterval(() => setFrame(`/api/camera/frame.jpg?t=${Date.now()}`), 300);
    return () => clearInterval(iv);
  }, [live]);
  if (!state?.test) return null;
  return (
    <Card title="Desktop camera" right={<Badge tone="info">USB doc cam</Badge>}
      sub="Plug a USB document camera or webcam into this PC — no phone needed. Lay the sheet flat and capture.">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Select value={dev} onChange={(e) => setDev(e.target.value)} className="max-w-[160px]">
          {(devices.length ? devices : [{ index: 0, label: "Camera 0" }]).map((d) => (
            <option key={d.index} value={d.index}>
              {d.label}{d.width ? ` · ${d.width}px` : ""}</option>))}
        </Select>
        <Button variant="ghost" icon={RefreshCw}
          onClick={() => api("/api/camera/devices").then(setDevices).catch(() => {})}>Detect</Button>
        {live
          ? <Button variant="ghost" icon={Square} onClick={async () => {
              await api("/api/camera/stop", { method: "POST" }); setLive(false); }}>Stop</Button>
          : <Button icon={Camera} loading={busy} onClick={async () => {
              setBusy(true);
              try {
                const r = await api("/api/camera/start", { method: "POST",
                  body: JSON.stringify({ index: +dev })});
                if (r.ok) setLive(true); else toast(r.message, "err");
              } catch (e) { toast(e.message, "err"); }
              setBusy(false); }}>Start</Button>}
      </div>
      {live && (
        <div>
          <img src={frame} alt="camera frame"
            className="w-full rounded border border-hair2 bg-black"/>
          <Button variant="ok" icon={Check} className="mt-2 w-full"
            onClick={async () => {
              try {
                await api("/api/camera/grade", { method: "POST" });
                toast("Frame captured — grading", "ok");
              } catch (e) { toast(e.data?.error?.message || e.message, "err"); }
            }}>Capture & grade this sheet</Button>
        </div>
      )}
    </Card>
  );
}

/* ================= WebRTC mirror — full lifecycle states =================
   idle → connecting (offer posted, waiting for a phone) → live → error.
   The video element is attached via ref inside ontrack (React re-renders
   can never blank it) and every state is visible + stoppable. */
function MirrorPanel() {
  const [phase, setPhase] = useState("idle"); // idle|connecting|live|error
  const [err, setErr] = useState("");
  const videoRef = useRef(null);
  const pcRef = useRef(null);
  const pollRef = useRef(null);
  const liveTimerRef = useRef(null);

  const detachVideo = () => {
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };
  const stopAll = useCallback(() => {
    clearInterval(pollRef.current);
    clearTimeout(liveTimerRef.current);
    if (pcRef.current) try { pcRef.current.close(); } catch {}
    pcRef.current = null;
    detachVideo();
    api("/api/mirror/offer", { method: "DELETE" }).catch(() => {});
    api("/api/mirror/answer", { method: "DELETE" }).catch(() => {});
    api("/api/mirror/bye", { method: "POST", body: "{}" }).catch(() => {});
    setPhase("idle");
  }, []);
  useEffect(() => stopAll, [stopAll]);

  const markLive = useCallback(() => {
    clearTimeout(liveTimerRef.current);
    setPhase((p) => (p === "live" ? p : "live"));
  }, []);

  const start = async () => {
    stopAll();
    setPhase("connecting"); setErr("");
    try {
      await api("/api/mirror/offer", { method: "DELETE" });
      await api("/api/mirror/answer", { method: "DELETE" });
      await api("/api/mirror/bye", { method: "DELETE" });
      const pc = new RTCPeerConnection();
      pcRef.current = pc;
      pc.addTransceiver("video", { direction: "recvonly" });

      pc.ontrack = (e) => {
        const v = videoRef.current;
        if (!v) return;
        v.srcObject = e.streams[0];
        v.play().catch(() => {});
        // live as soon as frames actually render — plus a delayed probe for
        // browsers that never fire `playing` on muted autoplay
        v.onplaying = markLive;
        clearTimeout(liveTimerRef.current);
        liveTimerRef.current = setTimeout(() => {
          if (v.readyState >= 2 && v.videoWidth > 0) markLive();
        }, 1200);
      };
      const onIceState = () => {
        const cs = pc.connectionState, is = pc.iceConnectionState;
        if (cs === "connected" || cs === "completed" ||
            is === "connected" || is === "completed") markLive();
        if (cs === "failed" || is === "failed" || cs === "disconnected") {
          setErr("Connection lost — the phone left or the network changed.");
          setPhase("error");
        }
      };
      pc.onconnectionstatechange = onIceState;
      pc.oniceconnectionstatechange = onIceState;

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      // gather ICE: up to 3 s (multi-interface machines are slow); post
      // whatever we have after that — host candidates dominate on a LAN
      await new Promise((res) => {
        const t = setTimeout(res, 3000);
        if (pc.iceGatheringState === "complete") { clearTimeout(t); res(); return; }
        pc.addEventListener("icegatheringstatechange", () => {
          if (pc.iceGatheringState === "complete") { clearTimeout(t); res(); }
        }, { once: true });
      });
      if (!pcRef.current) return;                 // stopped while gathering
      await api("/api/mirror/offer", { method: "POST",
        body: JSON.stringify(pc.localDescription) });

      let waited = 0;
      clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        waited += 1;
        if (waited > 50 || !pcRef.current) {      // ~45 s with no answer
          clearInterval(pollRef.current);
          if (pcRef.current) {
            setErr("Nothing connected in time — open the camera on the phone, "
                   + "tap its mirror button, then retry.");
            setPhase("error");
          }
          return;
        }
        try {
          const r = await api("/api/mirror/answer");
          if (r.payload && pcRef.current &&
              pc.signalingState === "have-local-offer") {
            await api("/api/mirror/answer", { method: "DELETE" }); // one-shot
            await pc.setRemoteDescription(r.payload);
            clearInterval(pollRef.current);
            // safety net: if ICE settles but no frame probe ran
            clearTimeout(liveTimerRef.current);
            liveTimerRef.current = setTimeout(() => {
              const v = videoRef.current;
              if (v && v.readyState >= 2 && v.videoWidth > 0) markLive();
              else if (pcRef.current && pc.connectionState !== "connected") {
                setErr("Connected but no video arrived — try again.");
                setPhase("error");
              }
            }, 3500);
          }
        } catch {}
      }, 900);
    } catch (e) {
      setErr(e.message || "Could not start the mirror.");
      setPhase("error");
    }
  };

  const LABEL = {
    idle: "Start monitoring", connecting: "Waiting for a phone…",
    live: "Live — stop", error: "Retry",
  };
  return (
    <Card title="Phone mirror" right={
      phase === "live" ? <LiveBadge>live</LiveBadge>
        : phase === "connecting" ? <Badge tone="warn">connecting</Badge>
        : phase === "error" ? <Badge tone="err">error</Badge> : null}
      sub="Open the camera on the phone and tap its mirror button — the live
           viewfinder appears here so framing can be checked at a glance.">
      <div className="flex flex-col items-stretch gap-3">
        <div className="relative overflow-hidden rounded border border-hair2 bg-black"
          style={{ minHeight: 120 }}>
          <video ref={videoRef} autoPlay muted playsInline
            className={`w-full ${phase === "live" ? "" : "hidden"}`}/>
          {phase !== "live" && (
            <div className="absolute inset-0 flex flex-col items-center
              justify-center gap-2 p-4 text-center">
              {phase === "connecting" && (
                <>
                  <div className="livedot h-2.5 w-2.5 rounded-full bg-brand"/>
                  <p className="text-[12px] text-ink2">Waiting for a phone…<br/>
                    <span className="text-[11px] text-ink3">tap the ⌁ mirror button in the camera view</span></p>
                </>
              )}
              {phase === "idle" && (
                <p className="flex items-center gap-2 text-[12px] text-ink3">
                  <MonitorUp size={16}/> Not monitoring</p>)}
              {phase === "error" && (
                <p className="max-w-xs text-[11.5px] leading-snug text-err">{err}</p>)}
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <Button className="flex-1"
            variant={phase === "live" || phase === "error" ? "danger" : "primary"}
            icon={phase === "live" || phase === "error" ? Square : MonitorUp}
            disabled={phase === "connecting"}
            onClick={phase === "idle" ? start : stopAll}>
            {LABEL[phase]}</Button>
        </div>
      </div>
    </Card>
  );
}

/* ================= activity log ================= */
function LogPanel() {
  const { state } = useApp();
  const boxRef = useRef(null);
  const log = state?.log || [];
  useEffect(() => {
    if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight;
  }, [log.length]);
  return (
    <Card title="Live activity"
      sub="Photos arrive over your Wi-Fi and are graded locally in under 150 ms.">
      <div ref={boxRef}
        className="h-[340px] overflow-y-auto rounded bg-base p-3 text-[11.5px]
          leading-relaxed">
        {!log.length
          ? <span className="text-ink3">waiting for the first sheet…</span>
          : log.map((ev, i) => {
              const t = new Date((ev.ts || 0) * 1000).toTimeString().slice(0, 8);
              let txt = "", tone = "text-ink2";
              if (ev.type === "log") { txt = ev.message;
                if (ev.level === "warn" || String(ev.message).startsWith("⚠")) tone = "text-warn"; }
              else if (ev.type === "sheet_graded")
                { txt = `${ev.result.student_id || "(no ID)"} graded — ${ev.result.score}/${ev.result.max_score} · ${ev.result.duration_ms} ms`; tone = "text-ok"; }
              else if (ev.type === "sheet_flagged")
                { txt = `${ev.result.student_id || "(no ID)"} flagged (${ev.result.flags.length}) → review queue`; tone = "text-warn"; }
              else if (ev.type === "sheet_rejected")
                { txt = `rejected [${ev.code}] ${ev.message}`; tone = "text-err"; }
              else if (ev.type === "review_resolved")
                { txt = `review resolved — ${ev.student_id || "?"} ${ev.score} pts → CSV`; tone = "text-ok"; }
              else if (ev.type === "server_started") { txt = "server started — " + (ev.url || ""); tone = "text-ok"; }
              else if (ev.type === "server_stopped") txt = "server stopped";
              else return null;
              return (
                <div key={i} className="flex gap-2.5">
                  <span className="tnum shrink-0 text-[10px] text-ink3">{t}</span>
                  <span className={tone}>{txt}</span>
                </div>
              );
            })}
      </div>
    </Card>
  );
}

export default function Serve() {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,370px)_minmax(0,1fr)]">
      <div className="space-y-4"><QrPanel/></div>
      <div className="space-y-4"><KeyCard/><CameraPanel/><MirrorPanel/><LogPanel/></div>
    </div>
  );
}
