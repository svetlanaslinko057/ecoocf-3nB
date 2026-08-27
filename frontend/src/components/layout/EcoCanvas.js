import React, { useEffect, useRef } from "react";

/**
 * EcoCanvas — subtle WebGL-grade background accent rendered on a raw 2D canvas.
 *
 * Floema-style atmosphere: a sparse field of soft, slow-drifting "pollen"
 * motes in deep-green / leaf tones at very low opacity. It is an *accent*,
 * never the hero — no blobs, no noise shaders, no distortion.
 *
 * Implemented with a plain <canvas> (not @react-three/fiber) on purpose:
 * react-three-fiber@9 + React 19 has a known `insertBefore` reconciler crash
 * that can tear down the whole document tree. A hand-rolled canvas loop gives
 * the same atmospheric layer with zero crash risk and a tiny GPU/CPU budget.
 *
 * Honors prefers-reduced-motion and coarse (touch) pointers by rendering
 * nothing. DPR is capped and the loop pauses when the tab is hidden.
 */
export default function EcoCanvas() {
  // DISABLED (per request): the floating "pollen motes" background accent is
  // turned off. The full implementation is kept below intact but inactive —
  // flip ECO_CANVAS_ENABLED back to true to re-enable it.
  const ECO_CANVAS_ENABLED = false;

  const canvasRef = useRef(null);

  useEffect(() => {
    if (!ECO_CANVAS_ENABLED) return undefined;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    if (reduce || coarse) return undefined;

    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;

    const COLORS = ["62,159,87", "95,143,74", "47,93,61"]; // leaf → deep green (de-toxified)
    const COUNT = 54;
    let w = 0;
    let h = 0;
    let dpr = 1;
    let raf = 0;
    let motes = [];
    let running = true;

    const rand = (a, b) => a + Math.random() * (b - a);

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = canvas.clientWidth || window.innerWidth;
      h = canvas.clientHeight || window.innerHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const spawn = () => {
      motes = Array.from({ length: COUNT }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        r: rand(0.6, 2.6),
        a: rand(0.04, 0.13),
        vy: -rand(0.05, 0.22),
        vx: rand(-0.06, 0.06),
        ph: Math.random() * Math.PI * 2,
        sway: rand(0.06, 0.2),
        c: COLORS[(Math.random() * COLORS.length) | 0],
      }));
    };

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      for (const m of motes) {
        m.ph += 0.01;
        m.y += m.vy;
        m.x += m.vx + Math.sin(m.ph) * m.sway;
        if (m.y < -12) {
          m.y = h + 12;
          m.x = Math.random() * w;
        }
        if (m.x < -12) m.x = w + 12;
        else if (m.x > w + 12) m.x = -12;

        const rad = m.r * 4;
        const g = ctx.createRadialGradient(m.x, m.y, 0, m.x, m.y, rad);
        g.addColorStop(0, `rgba(${m.c},${m.a})`);
        g.addColorStop(1, `rgba(${m.c},0)`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(m.x, m.y, rad, 0, Math.PI * 2);
        ctx.fill();
      }
      if (running) raf = requestAnimationFrame(draw);
    };

    const onVisibility = () => {
      if (document.hidden) {
        running = false;
        cancelAnimationFrame(raf);
      } else if (!running) {
        running = true;
        raf = requestAnimationFrame(draw);
      }
    };

    resize();
    spawn();
    raf = requestAnimationFrame(draw);
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  if (!ECO_CANVAS_ENABLED) return null;
  return <canvas ref={canvasRef} className="cine-canvas" aria-hidden="true" />;
}
