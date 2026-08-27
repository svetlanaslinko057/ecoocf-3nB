import React, { useMemo } from "react";

// A tiny, soft leaf glyph (organic, rounded) — drawn with currentColor.
const LeafGlyph = () => (
  <svg viewBox="0 0 24 24" width="100%" height="100%" fill="currentColor" aria-hidden="true">
    <path d="M21 3c0 9-5.5 14.5-13 15.5C5 19 3 16.5 3 13 3 7 9 3 21 3z" opacity="0.92" />
    <path d="M16 7c-4 2-7 5.5-9.5 11.5" stroke="rgba(255,255,255,0.35)" strokeWidth="0.7" fill="none" />
  </svg>
);

const TONES = ["#7FA653", "#5E8C3E", "#9CB87A", "#6E9A47", "#A8C481"];

/**
 * LeafFall — an unobtrusive ambient layer of slowly falling leaves rendered
 * behind the auth form on the light panel. Pure CSS keyframes (no rAF), low
 * opacity, and fully disabled under prefers-reduced-motion.
 */
export default function LeafFall({ count = 14 }) {
  const leaves = useMemo(() => {
    const rand = (a, b) => a + Math.random() * (b - a);
    return Array.from({ length: count }, (_, i) => ({
      id: i,
      left: rand(2, 96),
      size: rand(12, 26),
      dur: rand(13, 26),
      delay: -rand(0, 24),
      sway: `${rand(-60, 60).toFixed(0)}px`,
      op: rand(0.07, 0.2).toFixed(2),
      spin: Math.random() > 0.5 ? 1 : -1,
      tone: TONES[i % TONES.length],
    }));
  }, [count]);

  return (
    <div className="leaf-fall" aria-hidden="true">
      {leaves.map((l) => (
        <span
          key={l.id}
          className="leaf"
          style={{
            left: `${l.left}%`,
            width: `${l.size}px`,
            height: `${l.size}px`,
            color: l.tone,
            animationDuration: `${l.dur}s`,
            animationDelay: `${l.delay}s`,
            "--sway": l.sway,
            "--op": l.op,
            "--spin": `${l.spin * 360}deg`,
          }}
        >
          <LeafGlyph />
        </span>
      ))}
    </div>
  );
}
