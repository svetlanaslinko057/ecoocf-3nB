/**
 * useReveal — IntersectionObserver hook adding data-reveal="in" once visible.
 * Honors prefers-reduced-motion (no animation; element starts visible).
 */
import { useEffect, useRef } from "react";

export default function useReveal({ threshold = 0.15, rootMargin = "0px 0px -10% 0px", once = true } = {}) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const prefersReduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) { el.setAttribute("data-reveal", "in"); return; }
    el.setAttribute("data-reveal", "");
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.setAttribute("data-reveal", "in");
            if (once) obs.unobserve(e.target);
          } else if (!once) {
            e.target.setAttribute("data-reveal", "");
          }
        }
      },
      { threshold, rootMargin }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold, rootMargin, once]);
  return ref;
}
