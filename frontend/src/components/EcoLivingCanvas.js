import React, { useEffect, useRef } from "react";

/**
 * EcoLivingCanvas — a calm, long-running ECO animation for the auth aside.
 *
 * Concept: two rising "streams" of matter flow from the bottom upward. As each
 * particle climbs it transmutes from a dull amber/ochre tone (raw / hazardous
 * waste) into a clean lime-green (safely restored), drifting on a slow sine.
 * Behind them, soft vertical light beams breathe, and faint filaments connect
 * neighbouring motes — an unhurried metaphor for utilisation → restoration.
 *
 * It is deliberately slow and continuous (no twitching). Respects
 * prefers-reduced-motion by painting a single static composition.
 */
export default function EcoLivingCanvas() {
  const canvasRef = useRef(null);
  const rafRef = useRef(0);
  const stateRef = useRef({ w: 0, h: 0, dpr: 1, particles: [], beams: [], t: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ── tone helpers ────────────────────────────────────────────────────
    // progress p in [0,1]: bottom (raw amber) → top (restored lime)
    const toneAt = (p, a) => {
      // amber #C99A3A → leaf #7FB539 → lime #A3E635
      let r, g, b;
      if (p < 0.5) {
        const k = p / 0.5;
        r = 201 + (127 - 201) * k;
        g = 154 + (181 - 154) * k;
        b = 58 + (57 - 58) * k;
      } else {
        const k = (p - 0.5) / 0.5;
        r = 127 + (163 - 127) * k;
        g = 181 + (230 - 181) * k;
        b = 57 + (53 - 57) * k;
      }
      return `rgba(${r | 0},${g | 0},${b | 0},${a})`;
    };

    const rand = (min, max) => min + Math.random() * (max - min);

    const spawn = (h, atBottom = true) => {
      const stream = Math.random() < 0.5 ? 0 : 1; // two columns
      return {
        stream,
        baseX: stream === 0 ? 0.34 : 0.66, // fraction of width
        spread: rand(-0.13, 0.13),
        y: atBottom ? rand(1.0, 1.25) : rand(0, 1), // fraction of height (1 = bottom)
        speed: rand(0.00020240, 0.00050600), // −8%: gentler, smoother upward climb
        size: rand(1.4, 4.6),
        sway: rand(8, 34),
        swaySpeed: rand(0.4, 1.1),
        phase: rand(0, Math.PI * 2),
        glow: Math.random() < 0.22,
      };
    };

    const setup = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(1, rect.width);
      const h = Math.max(1, rect.height);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const s = stateRef.current;
      s.w = w;
      s.h = h;
      s.dpr = dpr;
      const count = Math.round(Math.min(150, Math.max(70, (w * h) / 5200)));
      s.particles = Array.from({ length: count }, () => spawn(h, false));
      s.beams = [
        { x: 0.34, width: 0.2, phase: 0 },
        { x: 0.66, width: 0.22, phase: Math.PI },
      ];
    };

    const drawBackground = () => {
      const { w, h } = stateRef.current;
      const g = ctx.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, "#0B1A14");
      g.addColorStop(0.55, "#0C2018");
      g.addColorStop(1, "#0E2B1E");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);

      // soft top-left radial glow
      const rg = ctx.createRadialGradient(w * 0.3, h * 0.12, 0, w * 0.3, h * 0.12, h * 0.7);
      rg.addColorStop(0, "rgba(163,230,53,0.10)");
      rg.addColorStop(1, "rgba(163,230,53,0)");
      ctx.fillStyle = rg;
      ctx.fillRect(0, 0, w, h);
    };

    const drawBeams = (t) => {
      const { w, h, beams } = stateRef.current;
      beams.forEach((b) => {
        const pulse = 0.5 + 0.5 * Math.sin(t * 0.0006 + b.phase);
        const cx = b.x * w;
        const bw = b.width * w;
        const grad = ctx.createLinearGradient(0, h, 0, 0);
        grad.addColorStop(0, `rgba(47,93,61,${0.0})`);
        grad.addColorStop(0.4, `rgba(60,140,80,${0.05 + pulse * 0.05})`);
        grad.addColorStop(1, `rgba(163,230,53,${0.0})`);
        ctx.fillStyle = grad;
        ctx.fillRect(cx - bw / 2, 0, bw, h);
      });
    };

    const draw = (t) => {
      const s = stateRef.current;
      const { w, h, particles } = s;
      drawBackground();
      drawBeams(t);

      // filaments between close particles in the same stream
      ctx.lineWidth = 1;
      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        const ax = a.baseX * w + (a.spread * w) + Math.sin(t * 0.001 * a.swaySpeed + a.phase) * a.sway;
        const ay = a.y * h;
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j];
          if (b.stream !== a.stream) continue;
          const bx = b.baseX * w + (b.spread * w) + Math.sin(t * 0.001 * b.swaySpeed + b.phase) * b.sway;
          const by = b.y * h;
          const dx = ax - bx;
          const dy = ay - by;
          const d2 = dx * dx + dy * dy;
          if (d2 < 5200) {
            const p = 1 - a.y;
            ctx.strokeStyle = toneAt(p, 0.05 * (1 - d2 / 5200));
            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(bx, by);
            ctx.stroke();
          }
        }
      }

      // particles
      particles.forEach((pt) => {
        const x = pt.baseX * w + (pt.spread * w) + Math.sin(t * 0.001 * pt.swaySpeed + pt.phase) * pt.sway;
        const y = pt.y * h;
        const prog = Math.min(1, Math.max(0, 1 - pt.y)); // 0 bottom → 1 top
        const edgeFade = Math.min(1, pt.y * 4) * Math.min(1, (1 - prog) * 6 + 0.25);
        const alpha = 0.22 + prog * 0.6;

        if (pt.glow) {
          const gr = ctx.createRadialGradient(x, y, 0, x, y, pt.size * 6);
          gr.addColorStop(0, toneAt(prog, 0.5 * edgeFade));
          gr.addColorStop(1, toneAt(prog, 0));
          ctx.fillStyle = gr;
          ctx.beginPath();
          ctx.arc(x, y, pt.size * 6, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.fillStyle = toneAt(prog, alpha * edgeFade);
        ctx.beginPath();
        ctx.arc(x, y, pt.size, 0, Math.PI * 2);
        ctx.fill();
      });
    };

    const step = (t) => {
      const s = stateRef.current;
      s.t = t;
      const dt = 16.7;
      s.particles.forEach((pt) => {
        pt.y -= pt.speed * dt;
        if (pt.y < -0.05) {
          Object.assign(pt, spawn(s.h, true)); // respawn at bottom
        }
      });
      draw(t);
      rafRef.current = requestAnimationFrame(step);
    };

    setup();
    if (reduced) {
      // static frame
      draw(1200);
    } else {
      rafRef.current = requestAnimationFrame(step);
    }

    const ro = new ResizeObserver(() => {
      setup();
      if (reduced) draw(1200);
    });
    ro.observe(canvas);

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} className="eco-living__canvas" aria-hidden="true" />;
}
