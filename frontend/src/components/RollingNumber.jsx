import { useEffect, useRef, useState, useMemo } from "react";
import styles from "./RollingNumber.module.css";

/**
 * RollingNumber — slot-machine style counter that ticks up to a target and
 * STOPS. Designed for hero KPIs like "Over 5,000 cars" — feels alive while
 * loading, then settles to a static final value (no looping, like a real
 * counter winding to completion).
 *
 * Props:
 *   target        — final number to land on (default 5000). Pulled from
 *                   admin-managed copy via the `renderKpiWithRolling` helper.
 *   span          — how many units the counter ticks through before settling
 *                   on the target (default 5 → e.g. 4,995 → 5,000 for a
 *                   target of 5,000; or 0 → 5 if the admin sets target to 5).
 *                   Automatically clamped to `target` so small numbers still
 *                   start at zero instead of going negative.
 *   tickMs        — milliseconds between ticks (default 1500 — measured pace).
 *   className     — passthrough class for the wrapper.
 *
 * Once the counter reaches `target` it stays there — no rewind, no reset.
 * Renders each digit inside a vertically translated column of 0-9 so the
 * transition between digits feels like a polished odometer / slot reel.
 */
const DIGITS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];

/**
 * DigitColumn — slot reel for a single digit.
 *
 * Always rotates FORWARD (like a real odometer): going from 9 → 0 slides
 * the reel one more position down instead of unwinding backwards through
 * 8-7-6-…-0. Implemented by stacking an extra "0" cell beneath the 0-9
 * column and snapping the reel back to the top after the wrap animation
 * finishes (with `transition: none`, so the snap is invisible).
 *
 * Backwards changes (e.g. 5,000 → 4,997 at the end of a cycle) skip
 * straight to the destination without any animation so the carousel reset
 * reads as an instant "rewind" rather than a long spin backwards.
 */
const DigitColumn = ({ digit }) => {
  const [step, setStep] = useState(digit);
  const prevDigit = useRef(digit);
  const elRef = useRef(null);

  // Whenever the incoming digit changes, decide how to move the reel.
  useEffect(() => {
    const prev = prevDigit.current;
    if (digit === prev) return;
    prevDigit.current = digit;

    const isWrap = prev === 9 && digit === 0;
    const isForward = digit > prev;

    if (isForward) {
      setStep((s) => s + (digit - prev));
    } else if (isWrap) {
      // Slide forward into the wrap-around "0" cell at the end of the reel.
      setStep((s) => s + 1);
    } else {
      // Backward jump (e.g. counter loop reset). Skip the animation so it
      // feels like an instant rewind, not a slow spin in the wrong direction.
      const el = elRef.current;
      if (!el) {
        setStep(digit);
        return;
      }
      el.style.transition = "none";
      setStep(digit);
      // Force reflow, then restore the transition on the next paint.
      // eslint-disable-next-line no-unused-expressions
      el.offsetHeight;
      requestAnimationFrame(() => {
        if (el) el.style.transition = "";
      });
    }
  }, [digit]);

  // When the reel has rolled into its wrap-around cell, snap it back to
  // position 0 (without animation) so the next forward step animates from
  // the correct starting point.
  useEffect(() => {
    if (step < 10) return;
    const t = window.setTimeout(() => {
      const el = elRef.current;
      if (!el) return;
      el.style.transition = "none";
      setStep((s) => s % 10);
      // eslint-disable-next-line no-unused-expressions
      el.offsetHeight;
      requestAnimationFrame(() => {
        if (el) el.style.transition = "";
      });
    }, 660); // slightly longer than the column CSS transition (620ms)
    return () => window.clearTimeout(t);
  }, [step]);

  return (
    <span className={styles.digit} aria-hidden="true">
      <span
        ref={elRef}
        className={styles.column}
        style={{ transform: `translateY(-${step}em)` }}
      >
        {/* 11 cells: 0-9 followed by a wrap-around "0" so 9→0 rolls forward. */}
        {DIGITS.concat([0]).map((d, i) => (
          <span key={i} className={styles.cell}>{d}</span>
        ))}
      </span>
    </span>
  );
};

const formatNumber = (n) => n.toLocaleString("en-US");

const RollingNumber = ({
  target = 5000,
  span = 5,
  tickMs = 700,
  suffix = "",
  className = "",
}) => {
  // Clamp the cycle span so small admin-defined targets still animate
  // gracefully: a target of "5" cycles 0→5; "100" cycles 95→100; "5,000"
  // cycles 4,995→5,000. Span can never push the start below zero.
  const safeTarget = Math.max(0, Math.floor(target));
  const safeSpan = Math.max(1, Math.min(Math.floor(span), safeTarget));
  const startValue = safeTarget - safeSpan;

  const [value, setValue] = useState(startValue);
  // Once `frozen === true` the component renders a STATIC text node — no
  // DigitColumns are mounted at all, so the wrap-around snap-back logic
  // can never produce any visible micro-movement after the target is hit.
  const [frozen, setFrozen] = useState(false);
  const timerRef = useRef(null);
  const freezeTimerRef = useRef(null);
  const reducedMotion = useMemo(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  }, []);

  useEffect(() => {
    if (reducedMotion || safeTarget === 0) {
      setValue(safeTarget);
      setFrozen(true);
      return undefined;
    }

    let cancelled = false;
    let current = startValue;
    setValue(current);
    setFrozen(false);

    const tick = () => {
      if (cancelled) return;
      current += 1;
      setValue(current);
      // Reached the target — stop ticking permanently. No loop-back,
      // no reset. The counter lands on the final value and stays there,
      // like a real-world tally that has just finished counting.
      if (current >= safeTarget) {
        // After the last digit animation (≈620ms), the wrap-snap reset
        // (≈660ms) AND the suffix settle (≈320ms) all finish, swap to
        // a STATIC text node so the component is completely motionless
        // from here on out. A generous margin guarantees no in-flight
        // transitions get cut short by the JSX swap.
        freezeTimerRef.current = window.setTimeout(() => {
          if (!cancelled) setFrozen(true);
        }, 1100);
        return;
      }
      timerRef.current = window.setTimeout(tick, tickMs);
    };

    timerRef.current = window.setTimeout(tick, tickMs);

    return () => {
      cancelled = true;
      if (timerRef.current) window.clearTimeout(timerRef.current);
      if (freezeTimerRef.current) window.clearTimeout(freezeTimerRef.current);
    };
  }, [safeTarget, startValue, tickMs, reducedMotion]);

  // Pad to the width of the target so the rendered character count is stable
  // (e.g. 4,995 and 5,000 both render as 5 chars, comma stays in place).
  const targetText = formatNumber(safeTarget);
  const valueText = formatNumber(value).padStart(targetText.length, " ");

  const suffixVisible = !!suffix && (frozen || value >= safeTarget);

  // STATIC mode — no animations, no slot reels, no possible micro-jitter.
  // The suffix is rendered as PLAIN inline text (no `.suffix` class, no
  // transition, no transform) so neither the bouncy pop-in ease nor a
  // mount/unmount class swap can produce any post-target wobble.
  if (frozen) {
    return (
      <span
        className={[styles.rolling, className].filter(Boolean).join(" ")}
        role="text"
        aria-label={`${targetText}${suffix || ""}`}
        data-testid="rolling-number"
        data-state="frozen"
      >
        <span className={styles.sep}>{`${targetText}${suffix || ""}`}</span>
      </span>
    );
  }

  return (
    <span
      className={[styles.rolling, className].filter(Boolean).join(" ")}
      role="text"
      aria-label={`${targetText}${suffix || ""}`}
      data-testid="rolling-number"
    >
      {valueText.split("").map((ch, idx) => {
        if (/\d/.test(ch)) {
          return <DigitColumn key={`${idx}-d`} digit={parseInt(ch, 10)} />;
        }
        if (ch === " ") {
          // leading space placeholder — keep layout stable when value shorter
          return (
            <span key={`${idx}-sp`} className={styles.spacer} aria-hidden="true">
              0
            </span>
          );
        }
        return (
          <span key={`${idx}-${ch}`} className={styles.sep} aria-hidden="true">
            {ch}
          </span>
        );
      })}
      {suffix && (
        <span
          className={`${styles.suffix} ${suffixVisible ? styles.suffixVisible : ""}`}
          aria-hidden={!suffixVisible}
        >
          {suffix}
        </span>
      )}
    </span>
  );
};

/**
 * Helper: replace the first numeric substring inside `text` with a rolling
 * version. Anything before/after the number is preserved as-is so localisation
 * ("/ Over 5,000 cars", "/ Над 5,000 автомобила") and admin-managed copy
 * keep working without any extra wiring — change the number in the admin
 * panel and the counter automatically retargets to the new value.
 *
 * If a "+" sign directly follows the number (e.g. "/ 500+ happy clients"),
 * it is captured and passed to RollingNumber as a `suffix` so it can be
 * revealed with a polished pop-in animation only after the counter lands
 * on the target.
 */
export const renderKpiWithRolling = (text, options = {}) => {
  if (typeof text !== "string") return text;
  // Capture an optional "+" immediately after the number so we can animate
  // it in once the rolling counter reaches the target value.
  const match = text.match(/([\d][\d,]*)(\+?)/);
  if (!match) return text;
  const numStr = match[1];
  const plus = match[2] || "";
  const before = text.slice(0, match.index);
  const after = text.slice(match.index + match[0].length);
  const numeric = parseInt(numStr.replace(/,/g, ""), 10);
  if (!Number.isFinite(numeric) || numeric <= 0) return text;
  return (
    <>
      {before}
      <RollingNumber target={numeric} suffix={plus} {...options} />
      {after}
    </>
  );
};

export default RollingNumber;
