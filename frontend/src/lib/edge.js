/** Anchor-lock viewfinder overlay — v2.
 *
 *  Mirrors the desktop engine's philosophy, on-device (~4–6 ms/frame):
 *   · local adaptive dark-threshold per corner ROI (handles uneven light),
 *   · flood-fill components + square filters → the 4 printed anchors,
 *   · EMA-smoothed anchor positions (no bracket jitter),
 *   · live quality telemetry (exposure, glare, focus, coverage, aspect),
 *   · diagonal-extremes perspective quad fallback when anchors are hidden,
 *   · dim-outside + sweep + capture countdown for auto-capture.
 */
export class EdgeOverlay {
  constructor(video, canvas, { onAlign, onAutoCapture, onQuality } = {}) {
    this.video = video; this.canvas = canvas;
    this.onAlign = onAlign; this.onAutoCapture = onAutoCapture;
    this.onQuality = onQuality;
    this.proc = document.createElement("canvas");
    this.proc.width = 176;
    this.run = false; this.timer = null;
    this.ema = null;                 // smoothed anchor positions
    this.hist = [];                  // raw positions (stability check)
    this.stable = 0; this.lastCap = 0; this.frames = 0;
    this.sweepT = 0;
  }
  start() {
    this.run = true; this.stable = 0; this.hist = []; this.ema = null;
    clearTimeout(this.timer);
    this.tick();
  }
  stop() { this.run = false; clearTimeout(this.timer); }

  tick() {
    if (!this.run) return;
    if (this.video.videoWidth > 0) {
      try { this.detect(); } catch { /* keep the camera usable */ }
    }
    this.timer = setTimeout(() => this.tick(), 120);
  }

  detect() {
    const v = this.video, W = this.proc.width;
    const H = Math.max(2, Math.round(W * v.videoHeight / v.videoWidth));
    if (this.proc.height !== H) this.proc.height = H;
    const g = this.proc.getContext("2d", { willReadFrequently: true });
    g.drawImage(v, 0, 0, W, H);
    const d = g.getImageData(0, 0, W, H).data;
    const lum = new Float32Array(W * H);
    let lsum = 0, glare = 0;
    for (let i = 0, j = 0; i < d.length; i += 4, j++) {
      const l = .299 * d[i] + .587 * d[i + 1] + .114 * d[i + 2];
      lum[j] = l; lsum += l;
      if (l > 242) glare++;
    }
    const n = W * H, mean = lsum / n;

    // focus estimate: mean |horizontal gradient| of a centre strip
    let grad = 0, gn = 0;
    const cy0 = (H * 0.35) | 0, cy1 = (H * 0.65) | 0;
    for (let y = cy0; y < cy1; y += 2)
      for (let x = 2; x < W - 2; x += 2) {
        grad += Math.abs(lum[y * W + x] - lum[y * W + x + 2]); gn++;
      }
    const sharp = gn ? grad / gn : 0;

    // ---- corner anchors: local adaptive threshold per ROI ----------------
    const ROIs = [[0, 0, .48, .44], [.52, 0, 1, .44],
                  [0, .56, .48, 1], [.52, .56, 1, 1]];
    const anchors = ROIs.map(([fx0, fy0, fx1, fy1]) => {
      const X0 = Math.floor(fx0 * W), X1 = Math.ceil(fx1 * W),
            Y0 = Math.floor(fy0 * H), Y1 = Math.ceil(fy1 * H);
      // Paper reference = 85th-percentile luminance of the ROI (sampled every
      // 2 px).  Unlike a plain mean this stays anchored to the *bright paper*
      // even when a shadow or glare band floods part of the corner, so the
      // dark anchor is always a fixed gap below the local paper — the threshold
      // rides along with the lighting instead of breaking under it.
      const samples = [];
      for (let y = Y0; y < Y1 - 1; y += 2)
        for (let x = X0; x < X1 - 1; x += 2) samples.push(lum[y * W + x]);
      samples.sort((a, b) => a - b);
      const paper = samples.length
        ? samples[Math.min(samples.length - 1, Math.floor(samples.length * 0.85))]
        : mean;
      // gap follows exposure: darker scene → smaller absolute gap, clamped so a
      // faint corner is never split and an overexposed paper never washes out.
      const darkTh = Math.min(120, Math.max(38, paper - 42));
      const seen = new Uint8Array(W * H);
      let best = null;
      for (let y = Y0; y < Y1; y++) for (let x = X0; x < X1; x++) {
        const i0 = y * W + x;
        if (lum[i0] >= darkTh || seen[i0]) continue;
        const stack = [i0]; seen[i0] = 1;
        let cnt = 0, sx = 0, sy = 0, bx0 = x, bx1 = x, by0 = y, by1 = y;
        while (stack.length) {
          const i = stack.pop(), iy = (i / W) | 0, ix = i - iy * W;
          cnt++; sx += ix; sy += iy;
          if (ix < bx0) bx0 = ix; if (ix > bx1) bx1 = ix;
          if (iy < by0) by0 = iy; if (iy > by1) by1 = iy;
          if (ix > X0) { const k = i - 1; if (lum[k] < darkTh && !seen[k]) { seen[k] = 1; stack.push(k); } }
          if (ix < X1 - 1) { const k = i + 1; if (lum[k] < darkTh && !seen[k]) { seen[k] = 1; stack.push(k); } }
          if (iy > Y0) { const k = i - W; if (lum[k] < darkTh && !seen[k]) { seen[k] = 1; stack.push(k); } }
          if (iy < Y1 - 1) { const k = i + W; if (lum[k] < darkTh && !seen[k]) { seen[k] = 1; stack.push(k); } }
        }
        const bw = bx1 - bx0 + 1, bh = by1 - by0 + 1, ar = bw / bh,
              fill = cnt / (bw * bh);
        const minS = Math.max(3, 0.022 * W), maxS = 0.085 * W;
        if (cnt >= 10 && bw >= minS && bw <= maxS && bh >= minS && bh <= maxS &&
            ar > 0.55 && ar < 1.8 && fill > 0.5) {
          const cx = sx / cnt, cy = sy / cnt;
          // prefer the candidate nearest the frame corner of this ROI
          const ri = (fx0 === 0 ? 0 : 1) + (fy0 === 0 ? 0 : 2);
          const tcx = ri % 2 ? W : 0, tcy = ri < 2 ? 0 : H;
          const dist = Math.hypot(cx - tcx, cy - tcy);
          if (!best || dist < best.score)
            best = { cx, cy, s: Math.max(bw, bh), score: dist };
        }
      }
      return best;
    });

    const all4 = anchors.every(Boolean);
    let quad = null, alignedNow = false, coverage = 0, aspect = 0;

    // Shape gate: the four raw anchors must make a plausible page quad.  A
    // stray false-positive corner (dark shadow blob / branding mark) throws the
    // diagonals off, so we refuse to lock onto it — the brackets keep hunting
    // rather than snapping to a wrong shape.  Distance-based tests are
    // mirror-invariant, so a front-facing camera still passes.
    let valid = false;
    if (all4) {
      const [a0, a1, a2, a3] = anchors;
      const d1 = Math.hypot(a2.cx - a0.cx, a2.cy - a0.cy);   // TL→BR
      const d2 = Math.hypot(a3.cx - a1.cx, a3.cy - a1.cy);   // TR→BL
      const topRaw = Math.hypot(a1.cx - a0.cx, a1.cy - a0.cy);
      const leftRaw = Math.hypot(a3.cx - a0.cx, a3.cy - a0.cy);
      const arRaw = topRaw / Math.max(1, leftRaw);
      const diagOk = Math.max(d1, d2) > 0 &&
        Math.abs(d1 - d2) / Math.max(d1, d2) < 0.45;
      valid = diagOk && arRaw > 0.45 && arRaw < 1.15;
    }

    if (all4 && valid) {
      // EMA smoothing — brackets glide instead of twitching
      if (!this.ema) this.ema = anchors.map((a) => ({ x: a.cx, y: a.cy, s: a.s }));
      const A = 0.42;
      anchors.forEach((a, i) => {
        this.ema[i].x += A * (a.cx - this.ema[i].x);
        this.ema[i].y += A * (a.cy - this.ema[i].y);
        this.ema[i].s += A * (a.s - this.ema[i].s);
      });
      const sm = this.ema.map((e) => ({ cx: e.x, cy: e.y, s: e.s }));
      quad = [sm[0], sm[1], sm[3], sm[2]];           // TL, TR, BR, BL

      this.hist.push(anchors.map((a) => ({ x: a.cx, y: a.cy })));
      if (this.hist.length > 6) this.hist.shift();
      let jitter = 0;
      if (this.hist.length >= 5) {
        for (let a = 0; a < 4; a++) {
          let mx = 1e9, Mx = -1, my = 1e9, My = -1;
          this.hist.forEach((f) => {
            mx = Math.min(mx, f[a].x); Mx = Math.max(Mx, f[a].x);
            my = Math.min(my, f[a].y); My = Math.max(My, f[a].y);
          });
          jitter = Math.max(jitter, Mx - mx, My - my);
        }
      }
      const top = Math.hypot(sm[1].cx - sm[0].cx, sm[1].cy - sm[0].cy);
      const left = Math.hypot(sm[3].cx - sm[0].cx, sm[3].cy - sm[0].cy);
      aspect = top / Math.max(1, left);
      let area = 0;
      for (let i = 0; i < 4; i++) {
        const p = quad[i], r = quad[(i + 1) % 4];
        area += p.cx * r.cy - r.cx * p.cy;
      }
      coverage = Math.abs(area / 2) / (W * H);
      const sharpOk = sharp > 2.0;
      alignedNow = this.hist.length >= 5 && jitter <= 3.0 && coverage > 0.20 &&
                   aspect > 0.5 && aspect < 1.05 && sharpOk;
      this.stable = alignedNow ? this.stable + 1 : 0;
    } else {
      this.ema = null; this.stable = 0; this.hist = [];
      quad = this.perspectiveFallback(lum, W, H);
    }

    // ---- telemetry ---------------------------------------------------------
    if (this.onQuality) {
      this.onQuality({
        anchors: anchors.filter(Boolean).length,
        exposure: mean < 55 ? "dark" : glare / n > 0.06 ? "glare" : "ok",
        focus: sharp < 1.6 ? "soft" : sharp > 14 ? "noisy" : "ok",
        coverage: Math.round(coverage * 100),
        aspect: +aspect.toFixed(2),
        sharp: +sharp.toFixed(1),
      });
    }

    this.draw(quad, alignedNow, W, H);

    if (alignedNow) {
      const need = 6;                              // stable frames to fire
      const left = Math.max(0, need - this.stable);
      this.onAlign?.("ok", left > 0 && this.autoCapWanted?.()
        ? `aligned — hold steady · ${left}` : "aligned — hold steady");
      if (this.autoCapWanted?.() && this.stable >= need &&
          Date.now() - this.lastCap > 4000) {
        this.lastCap = Date.now(); this.stable = 0;
        this.onAutoCapture?.();
      }
    } else {
      this.onAlign?.("hunt", all4 ? "almost — fill the frame"
                                  : "align the sheet in the frame");
    }
    this.frames++;
  }

  /** Perspective-ish quad from strong edges: pick the extreme strong-edge
   *  point along each diagonal from the centroid → 4-gon that follows tilt. */
  perspectiveFallback(lum, W, H) {
    let sum = 0, sq = 0, n = 0;
    const mag = new Float32Array(W * H);
    for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) {
      const i = y * W + x;
      const gx = -lum[i - W - 1] - 2 * lum[i - 1] - lum[i + W - 1]
                 + lum[i - W + 1] + 2 * lum[i + 1] + lum[i + W + 1];
      const gy = -lum[i - W - 1] - 2 * lum[i - W] - lum[i - W + 1]
                 + lum[i + W - 1] + 2 * lum[i + W] + lum[i + W + 1];
      const m = Math.hypot(gx, gy);
      mag[i] = m; sum += m; sq += m * m; n++;
    }
    const mean = sum / Math.max(1, n);
    const th = Math.max(60, mean + 1.7 * Math.sqrt(Math.max(0, sq / n - mean * mean)));
    const pts = [];
    for (let y = 2; y < H - 2; y += 2) for (let x = 2; x < W - 2; x += 2)
      if (mag[y * W + x] > th) pts.push([x, y]);
    if (pts.length < 40) return null;
    let cx = 0, cy = 0;
    pts.forEach((p) => { cx += p[0]; cy += p[1]; });
    cx /= pts.length; cy /= pts.length;
    const pick = (dx, dy) => {
      let best = null, bd = -1;
      for (const p of pts) {
        const d = (p[0] - cx) * dx + (p[1] - cy) * dy;
        if (d > bd) { bd = d; best = p; }
      }
      return best || [cx + dx * W * .3, cy + dy * H * .3];
    };
    const [tlx, tly] = pick(-1, -1), [trx, trY] = pick(1, -1),
          [blx, bly] = pick(-1, 1), [brx, bry] = pick(1, 1);
    return [{ cx: tlx, cy: tly }, { cx: trx, cy: trY },
            { cx: brx, cy: bry }, { cx: blx, cy: bly }];
  }

  draw(quad, aligned, W, H) {
    const cv = this.canvas, cw = cv.clientWidth || 1, ch = cv.clientHeight || 1;
    if (cv.width !== cw || cv.height !== ch) { cv.width = cw; cv.height = ch; }
    const c2 = cv.getContext("2d");
    c2.clearRect(0, 0, cw, ch);
    const kx = cw / W, ky = ch / H;
    const col = aligned ? "#45D691" : "#6D78F5";
    const dim = aligned ? 0.22 : 0.10;

    // path helper in screen space
    const path = () => {
      c2.beginPath();
      c2.moveTo(quad[0].cx * kx, quad[0].cy * ky);
      for (let i = 1; i < 4; i++) c2.lineTo(quad[i].cx * kx, quad[i].cy * ky);
      c2.closePath();
    };

    if (quad) {
      // dim everything outside the quad (clip-inverse fill)
      c2.save();
      path();
      c2.fillStyle = `rgba(4,6,10,${dim})`;
      c2.rect(0, 0, cw, ch);
      c2.fill("evenodd");
      c2.restore();

      // interior grid — one mid-line each way, reads like a scanning surface
      c2.save();
      path(); c2.clip();
      c2.strokeStyle = col; c2.globalAlpha = 0.18; c2.lineWidth = 1;
      const mx0 = (quad[0].cx + quad[3].cx) / 2, my0 = (quad[0].cy + quad[3].cy) / 2;
      const mx1 = (quad[1].cx + quad[2].cx) / 2, my1 = (quad[1].cy + quad[2].cy) / 2;
      c2.beginPath(); c2.moveTo(mx0 * kx, my0 * ky); c2.lineTo(mx1 * kx, my1 * ky);
      const nx0 = (quad[0].cx + quad[1].cx) / 2, ny0 = (quad[0].cy + quad[1].cy) / 2;
      const nx1 = (quad[3].cx + quad[2].cx) / 2, ny1 = (quad[3].cy + quad[2].cy) / 2;
      c2.moveTo(nx0 * kx, ny0 * ky); c2.lineTo(nx1 * kx, ny1 * ky); c2.stroke();
      c2.globalAlpha = 1;

      // ambient sweep while hunting (Sightline: one 3.4 s line)
      if (!aligned && this.run) {
        this.sweepT = (this.sweepT + 0.028) % 1.15;
        const t = this.sweepT < 1 ? this.sweepT : -0.15 + (this.sweepT - 1);
        const sx = quad.map((q) => q.cx);
        const xmin = Math.min(...sx) * kx, xmax = Math.max(...sx) * kx;
        const lx = xmin + (xmax - xmin) * t;
        const grd = c2.createLinearGradient(lx - 40, 0, lx + 40, 0);
        grd.addColorStop(0, "rgba(109,120,245,0)");
        grd.addColorStop(0.5, "rgba(154,176,255,0.30)");
        grd.addColorStop(1, "rgba(109,120,245,0)");
        c2.fillStyle = grd;
        c2.fillRect(lx - 40, 0, 80, ch);
      }
      c2.restore();

      // outline
      c2.lineWidth = 2; c2.strokeStyle = col;
      c2.setLineDash(aligned ? [] : [7, 5]);
      path(); c2.stroke(); c2.setLineDash([]);

      // corner brackets locked on the anchors (or fallback corners)
      quad.forEach((a) => {
        const s = Math.max(15, (a.s || 12) * 1.7) * ((kx + ky) / 2);
        const x = a.cx * kx, y = a.cy * ky;
        c2.lineWidth = 4; c2.strokeStyle = col; c2.lineCap = "round";
        [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([dx, dy]) => {
          c2.beginPath();
          c2.moveTo(x + dx * s, y + dy * s - dy * (s * 0.55));
          c2.lineTo(x + dx * s, y + dy * s);
          c2.lineTo(x + dx * s - dx * (s * 0.55), y + dy * s);
          c2.stroke();
        });
      });

      // centre reticle
      const cxs = (quad[0].cx + quad[2].cx) / 2 * kx,
            cys = (quad[0].cy + quad[2].cy) / 2 * ky;
      c2.strokeStyle = col; c2.globalAlpha = 0.7; c2.lineWidth = 1.5;
      c2.beginPath();
      c2.moveTo(cxs - 8, cys); c2.lineTo(cxs + 8, cys);
      c2.moveTo(cxs, cys - 8); c2.lineTo(cxs, cys + 8);
      c2.stroke(); c2.globalAlpha = 1;
    }
  }
}
