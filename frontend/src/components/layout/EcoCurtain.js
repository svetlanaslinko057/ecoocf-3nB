import React, { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import gsap from "gsap";

/**
 * EcoCurtain — premium page-transition wipe on route change (public only).
 * On each navigation the panel snaps to cover, then wipes away to reveal the
 * new page. Respects reduced-motion (no animation).
 */
export default function EcoCurtain() {
  const ref = useRef(null);
  const { pathname } = useLocation();
  const first = useRef(true);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (first.current) {
      first.current = false;
      gsap.set(el, { scaleY: 0 });
      return;
    }
    if (reduce) { gsap.set(el, { scaleY: 0 }); return; }
    gsap.killTweensOf(el);
    const tl = gsap.timeline();
    tl.set(el, { scaleY: 1, transformOrigin: "bottom" })
      .to(el, { scaleY: 0, transformOrigin: "top", duration: 0.7, ease: "expo.inOut", delay: 0.02 });
    return () => tl.kill();
  }, [pathname]);

  return <div className="eco-curtain" ref={ref} aria-hidden="true" />;
}
