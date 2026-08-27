/**
 * AnimatedHeading
 * -----------------------------------------------------------------------------
 * Universal section heading that applies the SITE-WIDE reveal animation:
 *
 *   "per-character diagonal slide-up"
 *      → every letter is wrapped in its own overflow:hidden mask
 *      → a block-level inner span starts at translateY(100%) opacity:0
 *      → animation-delay grows from left to right (configurable step)
 *      → ease-out-quint curve (smooth, no bounce, premium feel)
 *
 * Behaviour matches the hero "FROM AUCTION TO KEYS IN YOUR HANDS" treatment
 * implemented for the homepage hero — so the whole site speaks the same
 * visual language.
 *
 * Trigger: an IntersectionObserver fires ONCE when the heading first scrolls
 * into the viewport, then disconnects. This guarantees we never replay the
 * animation while scrolling back up.
 *
 * Accessibility:
 *   - aria-label exposes the full readable text on the wrapping element
 *   - individual char spans are aria-hidden
 *   - prefers-reduced-motion completely disables motion (see CSS)
 *
 * Props:
 *   as           default "h2"       — tag rendered as the heading
 *   text         REQUIRED            — string to animate
 *   className                        — passthrough class for typographic style
 *   style                            — passthrough style
 *   stepMs       default 28          — ms of delay added per character (slope)
 *   baseDelay    default 0           — ms before the first character starts
 *   durationMs   default 900         — per-char animation duration
 *   threshold    default 0.18        — IntersectionObserver threshold
 *   rootMargin   default "0px 0px -8% 0px"
 *   once         default true        — disconnect after first trigger
 *   onVisible                        — optional callback when revealed
 */
import React, { useEffect, useRef, useState, useMemo } from "react";
import styles from "./AnimatedHeading.module.css";

const AnimatedHeading = ({
  as: Tag = "h2",
  text,
  className = "",
  style,
  stepMs = 28,
  baseDelay = 0,
  durationMs = 900,
  /* Defaults tuned so the cascade only triggers once the user can ACTUALLY
   * see a meaningful portion of the heading. With the previous values
   * (`threshold: 0.18`, `rootMargin: "0px 0px -8% 0px"`) the IO fired while
   * the heading was still ~100 px below the viewport — meaning by the time
   * the user finished scrolling the animation was already half-done and
   * therefore perceived as "no animation". Bumping the threshold to 0.35
   * and removing the negative bottom rootMargin keeps the per-char wave
   * clearly visible to the user. The hero / above-the-fold titles still
   * trigger instantly via the `inViewAtMount` fast-path below, so this
   * change only affects headings deeper in the page. */
  threshold = 0.35,
  rootMargin = "0px 0px 0px 0px",
  once = true,
  onVisible,
  ...rest
}) => {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  // Cache the reduced-motion preference (the keyframes themselves are also
  // suppressed via @media, this is mostly so we don't even add the class).
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

    // If the element is already in view at mount (typical for hero / above-
    // the-fold), schedule the reveal immediately so it doesn't have to wait
    // for the next scroll tick.
    const rect = el.getBoundingClientRect();
    const inViewAtMount =
      rect.top < (window.innerHeight || 0) && rect.bottom > 0;

    if (inViewAtMount) {
      // Use rAF so the initial paint definitely shows the hidden state
      // before the animation begins (otherwise React 18 batching may
      // flash the final state).
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
            if (typeof onVisible === "function") onVisible();
          }
        });
      },
      { threshold, rootMargin }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reducedMotion, threshold, rootMargin, once, onVisible]);

  // Split into words → chars to keep words atomic on wrap.
  const str = String(text ?? "");
  const words = str.split(/(\s+)/); // keep whitespace tokens

  let charIndex = 0;
  return (
    <Tag
      ref={ref}
      className={`${styles.heading} ${visible ? styles.isVisible : ""} ${className}`}
      style={style}
      aria-label={str}
      {...rest}
    >
      {words.map((token, wi) => {
        if (/^\s+$/.test(token)) {
          return (
            <span key={`s-${wi}`} aria-hidden="true">
              {token}
            </span>
          );
        }
        const chars = [...token];
        return (
          <span
            key={`w-${wi}`}
            aria-hidden="true"
            className={styles.word}
          >
            {chars.map((ch, ci) => {
              const delay = baseDelay + charIndex * stepMs;
              charIndex += 1;
              return (
                <span key={`c-${wi}-${ci}`} className={styles.charMask}>
                  <span
                    className={styles.charInner}
                    style={{
                      animationDelay: `${delay}ms`,
                      animationDuration: `${durationMs}ms`,
                    }}
                  >
                    {ch}
                  </span>
                </span>
              );
            })}
          </span>
        );
      })}
    </Tag>
  );
};

export default AnimatedHeading;
