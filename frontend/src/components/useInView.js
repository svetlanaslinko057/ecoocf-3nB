/**
 * useInView — tiny IntersectionObserver hook.
 *
 * Returns `[ref, visible]`. Attach the ref to a DOM node; `visible` flips to
 * true the first time the node intersects the viewport (and stays true if
 * `once === true`). Honours `prefers-reduced-motion` by returning `true`
 * immediately.
 *
 * Used by Reveal / AnimatedHeading and any one-off section that wants to
 * gate animations on viewport entry without re-implementing the boilerplate.
 */
import { useEffect, useMemo, useRef, useState } from "react";

export default function useInView({
  threshold = 0.18,
  rootMargin = "0px 0px -8% 0px",
  once = true,
} = {}) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  const reducedMotion = useMemo(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  }, []);

  useEffect(() => {
    if (reducedMotion) {
      setVisible(true);
      return undefined;
    }
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return undefined;
    }

    const rect = el.getBoundingClientRect();
    const inViewAtMount =
      rect.top < (window.innerHeight || 0) && rect.bottom > 0;
    if (inViewAtMount) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => setVisible(true));
      });
      return undefined;
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setVisible(true);
            if (once) io.disconnect();
          }
        });
      },
      { threshold, rootMargin }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reducedMotion, threshold, rootMargin, once]);

  return [ref, visible];
}
