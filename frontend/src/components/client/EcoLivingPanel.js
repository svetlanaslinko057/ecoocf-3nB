/**
 * EcoLivingPanel — calm, premium "eco-regeneration" animation for the right
 * side of the client auth screens.
 *
 * Rewrite (2026-06): replaces the noisy ribbons + particle swarm with a much
 * calmer composition:
 *   1) a slow breathing aurora gradient (low-frequency sine of saturation/offset)
 *   2) three soft vertical light columns drifting at different paces
 *   3) ~16 sparse, large, slow motes that gently rise and fade — no chaos
 *   4) a subtle horizon glow at the bottom
 *
 * Time-based (no jitter), retina-aware, prefers-reduced-motion safe.
 */
import React, { useEffect, useRef } from "react";

export default function EcoLivingPanel({ pulseKey = 0 }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(0);
  const pulseRef = useRef(0);

  // brighten briefly when the auth step/tab changes (calm feedback)
  useEffect(() => {
    pulseRef.current = 1;
  }, [pulseKey]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let w = 0;
    let h = 0;
    let dpr = 1;

    // sparse motes: large, slow, never more than ~16
    const motes = Array.from({ length: 16 }, () => ({
      x: Math.random(),
      y: Math.random(),
      r: 1.2 + Math.random() * 2.4,
      sp: 0.00008280 + Math.random() * 0.00016560, // slowed ~2× — gentle drift (−8% rise for a calmer climb)
      drift: 0.06 + Math.random() * 0.10,
      phase: Math.random() * Math.PI * 2,
      alpha: 0.08 + Math.random() * 0.18,
    }));

    // 3 vertical light columns drifting horizontally at different rates
    const columns = [
      { base: 0.22, amp: 0.05, sp: 0.00004, hue: "lime" },
      { base: 0.52, amp: 0.08, sp: 0.00003, hue: "deep" },
      { base: 0.78, amp: 0.06, sp: 0.00006, hue: "lime" },
    ];

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = Math.max(1, Math.floor(rect.width));
      h = Math.max(1, Math.floor(rect.height));
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    // ── layer 1: deep base + slow breathing aurora ────────────────────────────
    const drawBase = (t, boost) => {
      // deep almost-black green base
      ctx.fillStyle = "#0B1A14";
      ctx.fillRect(0, 0, w, h);

      // breathing aurora: a soft radial gradient whose center slowly drifts
      const bx = w * (0.5 + Math.sin(t * 0.00006) * 0.18);
      const by = h * (0.42 + Math.cos(t * 0.000045) * 0.12);
      const breathe = 0.42 + Math.sin(t * 0.00012) * 0.08 + boost * 0.06;

      const aurora = ctx.createRadialGradient(bx, by, h * 0.08, bx, by, h * 0.95);
      aurora.addColorStop(0.0, `rgba(34, 86, 56, ${0.30 + breathe * 0.20})`);
      aurora.addColorStop(0.35, `rgba(22, 60, 42, ${0.18 + breathe * 0.12})`);
      aurora.addColorStop(1.0, "rgba(8, 16, 12, 0.0)");
      ctx.fillStyle = aurora;
      ctx.fillRect(0, 0, w, h);

      // subtle horizon glow at the bottom
      const horizon = ctx.createLinearGradient(0, h * 0.78, 0, h);
      horizon.addColorStop(0, "rgba(163, 230, 53, 0)");
      horizon.addColorStop(1, `rgba(163, 230, 53, ${0.05 + boost * 0.04})`);
      ctx.fillStyle = horizon;
      ctx.fillRect(0, 0, w, h);
    };

    // ── layer 2: 3 calm vertical light columns ────────────────────────────────
    const drawColumns = (t, boost) => {
      ctx.globalCompositeOperation = "lighter";
      for (const c of columns) {
        const cx = w * (c.base + Math.sin(t * c.sp) * c.amp);
        const widthCol = w * 0.18;
        const g = ctx.createLinearGradient(cx - widthCol, 0, cx + widthCol, 0);
        const a = c.hue === "lime"
          ? 0.045 + boost * 0.03
          : 0.07 + boost * 0.04;
        const color = c.hue === "lime" ? "163, 230, 53" : "47, 110, 70";
        g.addColorStop(0, `rgba(${color}, 0)`);
        g.addColorStop(0.5, `rgba(${color}, ${a})`);
        g.addColorStop(1, `rgba(${color}, 0)`);
        ctx.fillStyle = g;
        ctx.fillRect(cx - widthCol, 0, widthCol * 2, h);
      }
      ctx.globalCompositeOperation = "source-over";
    };

    // ── layer 3: sparse rising motes ──────────────────────────────────────────
    const drawMotes = (t, boost) => {
      ctx.globalCompositeOperation = "lighter";
      for (const m of motes) {
        m.y -= m.sp;
        if (m.y < -0.06) {
          m.y = 1.05;
          m.x = Math.random();
        }
        const sway = Math.sin(t * 0.0002 + m.phase) * m.drift;
        const px = (m.x + sway * 0.06) * w;
        const py = m.y * h;
        const r = m.r * (1 + boost * 0.4);

        // soft halo
        const grad = ctx.createRadialGradient(px, py, 0, px, py, r * 5);
        grad.addColorStop(0, `rgba(196, 240, 120, ${m.alpha * (0.9 + boost * 0.4)})`);
        grad.addColorStop(0.5, `rgba(163, 230, 53, ${m.alpha * 0.25})`);
        grad.addColorStop(1, "rgba(163, 230, 53, 0)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(px, py, r * 5, 0, Math.PI * 2);
        ctx.fill();

        // bright core
        ctx.fillStyle = `rgba(220, 250, 170, ${m.alpha * 1.5})`;
        ctx.beginPath();
        ctx.arc(px, py, r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
    };

    const renderStatic = () => {
      drawBase(0, 0);
      drawColumns(0, 0);
      drawMotes(0, 0);
    };

    if (reduce) {
      renderStatic();
      return () => ro.disconnect();
    }

    const loop = (now) => {
      // decay pulse softly (slower decay → calmer)
      pulseRef.current *= 0.98;
      const boost = pulseRef.current;
      drawBase(now, boost);
      drawColumns(now, boost);
      drawMotes(now, boost);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} className="eco-living__canvas" aria-hidden="true" />;
}
