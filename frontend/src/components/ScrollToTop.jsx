import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * ScrollToTop — react-router helper that forces every route navigation to
 * land at the top of the page.
 *
 * react-router-dom intentionally preserves the previous scroll offset when
 * the URL changes, which can leave the user mid-page after clicking a link
 * (the issue reported by the user: "очередные страницы меня кидают всегда
 * на середину страницы"). Mounting this component anywhere inside the
 * router restores the expected behaviour:
 *
 *   • Page transitions (different pathname) → scroll back to (0, 0).
 *   • In-page anchor links (with a `#hash`) are left untouched so the
 *     browser's native anchor scrolling still works.
 *   • Replace-state navigations (e.g. setting query params on the same
 *     page) are also left untouched — they should not yank the user back
 *     to the top.
 *
 * The reset uses `behavior: "auto"` (instant) so it feels like a normal
 * page load. We also reset `document.documentElement` and `document.body`
 * because some legacy CSS setups scroll on the body instead of the html
 * element.
 */
const ScrollToTop = () => {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    // Anchor links inside the same page — let the browser handle them.
    if (hash) return;

    // Use double-rAF so the new route's DOM has been painted before we
    // scroll. Some pages render their first frame at a tall height that
    // would otherwise be momentarily visible scrolled down.
    let raf2 = 0;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        window.scrollTo({ top: 0, left: 0, behavior: "auto" });
        if (document.documentElement) document.documentElement.scrollTop = 0;
        if (document.body) document.body.scrollTop = 0;
      });
    });
    return () => {
      cancelAnimationFrame(raf1);
      if (raf2) cancelAnimationFrame(raf2);
    };
  }, [pathname, hash]);

  return null;
};

export default ScrollToTop;
