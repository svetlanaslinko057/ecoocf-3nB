import React, { useEffect, useRef } from "react";

/**
 * EcoCursor — eco / regeneration-themed custom cursor.
 *
 * Composition:
 *   1) A small leaf-shaped head that points in the direction of movement.
 *   2) A flowing trail of 10 fading "seed motes" that follow the head with
 *      progressively lagged easing (like seeds drifting on wind).
 *   3) On hover over interactive elements, the leaf opens into a soft ring
 *      and the trail expands — communicating intent ("you can act here").
 *   4) On click, a brief burst of small particles emanates outward
 *      (like a seed bursting open) — confirming action.
 *
 * Disabled automatically on touch devices and when prefers-reduced-motion
 * is set (only the static dot remains for accessibility).
 */
const TRAIL_LENGTH = 10;

export default function EcoCursor() {
  const headRef = useRef(null);
  const ringRef = useRef(null);
  const trailRefs = useRef(Array.from({ length: TRAIL_LENGTH }, () => null));
  const containerRef = useRef(null);

  const target = useRef({ x: -200, y: -200 });
  const head = useRef({ x: -200, y: -200 });
  const trail = useRef(
    Array.from({ length: TRAIL_LENGTH }, () => ({ x: -200, y: -200 })),
  );
  const angle = useRef(0);
  const lastPos = useRef({ x: -200, y: -200, t: 0 });
  const hover = useRef(false);
  const pressed = useRef(false);
  const speed = useRef(0);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const isTouch = window.matchMedia("(pointer: coarse)").matches;
    if (isTouch) return undefined;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    document.body.classList.add("eco-has-cursor");

    const onMove = (e) => {
      target.current = { x: e.clientX, y: e.clientY };
      // hide the custom cursor near the system scrollbar to avoid visual confusion
      const onScrollbar = e.clientX >= window.innerWidth - 16;
      if (containerRef.current) {
        containerRef.current.dataset.away = onScrollbar ? "1" : "0";
      }
      const now = performance.now();
      const dx = e.clientX - lastPos.current.x;
      const dy = e.clientY - lastPos.current.y;
      const dt = Math.max(1, now - lastPos.current.t);
      const dist = Math.hypot(dx, dy);
      // smoothed speed (0..1 mapped to ~0..40 px/frame)
      const inst = Math.min(1, dist / (dt * 0.5));
      speed.current += (inst - speed.current) * 0.25;
      if (dist > 0.6) {
        const a = Math.atan2(dy, dx) * (180 / Math.PI);
        // ease angle to avoid jitter
        let delta = a - angle.current;
        while (delta > 180) delta -= 360;
        while (delta < -180) delta += 360;
        angle.current += delta * 0.25;
      }
      lastPos.current = { x: e.clientX, y: e.clientY, t: now };

      const el = e.target?.closest?.(
        "a, button, [role='button'], [data-cursor], input, textarea, select, label[for]",
      );
      hover.current = !!el;
      if (containerRef.current) {
        containerRef.current.dataset.hover = hover.current ? "1" : "0";
      }
    };

    const onDown = () => {
      pressed.current = true;
      if (containerRef.current) containerRef.current.dataset.press = "1";
      // burst particles
      if (containerRef.current) {
        const burst = document.createElement("span");
        burst.className = "eco-cursor__burst";
        burst.style.left = `${target.current.x}px`;
        burst.style.top = `${target.current.y}px`;
        containerRef.current.appendChild(burst);
        // 7 outward seeds
        const seeds = 7;
        for (let i = 0; i < seeds; i += 1) {
          const s = document.createElement("i");
          const a = (Math.PI * 2 * i) / seeds + Math.random() * 0.3;
          const dist = 22 + Math.random() * 14;
          s.style.setProperty("--bx", `${Math.cos(a) * dist}px`);
          s.style.setProperty("--by", `${Math.sin(a) * dist}px`);
          s.style.setProperty("--rot", `${Math.random() * 360}deg`);
          burst.appendChild(s);
        }
        window.setTimeout(() => burst.remove(), 720);
      }
    };
    const onUp = () => {
      pressed.current = false;
      if (containerRef.current) containerRef.current.dataset.press = "0";
    };
    const onLeave = () => {
      if (containerRef.current) containerRef.current.dataset.away = "1";
    };
    const onEnter = () => {
      if (containerRef.current) containerRef.current.dataset.away = "0";
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerdown", onDown, { passive: true });
    window.addEventListener("pointerup", onUp, { passive: true });
    window.addEventListener("blur", onUp);
    document.addEventListener("mouseleave", onLeave);
    document.addEventListener("mouseenter", onEnter);

    // re-evaluate the hover target while scrolling — the element under the
    // cursor changes even though the mouse hasn't moved.
    const onScroll = () => {
      const el = document.elementFromPoint(target.current.x, target.current.y);
      const inter = el?.closest?.(
        "a, button, [role='button'], [data-cursor], input, textarea, select, label[for]",
      );
      hover.current = !!inter;
      if (containerRef.current) {
        containerRef.current.dataset.hover = hover.current ? "1" : "0";
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });

    let raf;
    const HEAD_LERP = 0.32;
    const TRAIL_BASE_LERP = 0.42;

    const loop = () => {
      // head follows the cursor tightly
      head.current.x += (target.current.x - head.current.x) * HEAD_LERP;
      head.current.y += (target.current.y - head.current.y) * HEAD_LERP;

      // each trail segment lerps toward the previous segment (or the head)
      let px = head.current.x;
      let py = head.current.y;
      for (let i = 0; i < TRAIL_LENGTH; i += 1) {
        const lerp = TRAIL_BASE_LERP - i * 0.028; // progressively slower
        const seg = trail.current[i];
        seg.x += (px - seg.x) * Math.max(0.08, lerp);
        seg.y += (py - seg.y) * Math.max(0.08, lerp);
        px = seg.x;
        py = seg.y;
        const node = trailRefs.current[i];
        if (node) {
          const t = 1 - i / TRAIL_LENGTH; // 1 at head, 0 at tail
          const size = 5 - i * 0.32;
          const op = 0.55 * t * (0.6 + speed.current * 0.6);
          node.style.transform = `translate3d(${seg.x}px, ${seg.y}px, 0) translate(-50%, -50%) scale(${Math.max(0.2, t)})`;
          node.style.opacity = `${op}`;
          node.style.width = `${Math.max(2, size)}px`;
          node.style.height = `${Math.max(2, size)}px`;
        }
      }

      // head (leaf) — rotate to movement direction; bloom on hover
      if (headRef.current) {
        const scale = hover.current ? 1.35 : 1;
        // leaf points in movement direction; add small lift on press
        const press = pressed.current ? 0.85 : 1;
        headRef.current.style.transform =
          `translate3d(${head.current.x}px, ${head.current.y}px, 0) ` +
          `translate(-50%, -50%) rotate(${angle.current}deg) scale(${scale * press})`;
      }
      if (ringRef.current) {
        // a soft, breathing ring that grows on hover
        const s = hover.current ? 1 : 0.28;
        const op = hover.current ? 0.75 : 0;
        ringRef.current.style.transform =
          `translate3d(${head.current.x}px, ${head.current.y}px, 0) ` +
          `translate(-50%, -50%) scale(${s})`;
        ringRef.current.style.opacity = `${op}`;
      }

      raf = requestAnimationFrame(loop);
    };

    if (reduce) {
      // static placement only — no animation loop
      const apply = () => {
        if (headRef.current) {
          headRef.current.style.transform =
            `translate3d(${target.current.x}px, ${target.current.y}px, 0) translate(-50%, -50%)`;
        }
      };
      window.addEventListener("pointermove", apply, { passive: true });
      return () => {
        window.removeEventListener("pointermove", apply);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerdown", onDown);
        window.removeEventListener("pointerup", onUp);
        window.removeEventListener("blur", onUp);
        document.removeEventListener("mouseleave", onLeave);
        document.removeEventListener("mouseenter", onEnter);
        document.body.classList.remove("eco-has-cursor");
      };
    }

    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("blur", onUp);
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("mouseleave", onLeave);
      document.removeEventListener("mouseenter", onEnter);
      document.body.classList.remove("eco-has-cursor");
    };
  }, []);

  return (
    <div ref={containerRef} className="eco-cursor" aria-hidden="true" data-away="0" data-hover="0" data-press="0">
      {/* Trail — drawn behind the head */}
      {Array.from({ length: TRAIL_LENGTH }).map((_, i) => (
        <span
          key={`seed-${i}`}
          ref={(el) => { trailRefs.current[i] = el; }}
          className="eco-cursor__seed"
        />
      ))}
      {/* Soft "bloom" ring (only visible on hover) */}
      <div ref={ringRef} className="eco-cursor__bloom" />
      {/* Leaf head (always visible, rotates with motion) */}
      <div ref={headRef} className="eco-cursor__leaf">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
          {/* a stylised leaf — drop shape with a central vein */}
          <path
            d="M3 12c2.6-6.7 8-9.3 17-9 .3 9-2.3 14.4-9 17-4.7 1.8-8-1.5-8-8z"
            fill="currentColor"
            opacity="0.95"
          />
          <path
            d="M5.5 14.5C9 11 14 9 19 8"
            stroke="rgba(255,255,255,0.55)"
            strokeWidth="0.9"
            strokeLinecap="round"
          />
        </svg>
      </div>
    </div>
  );
}
