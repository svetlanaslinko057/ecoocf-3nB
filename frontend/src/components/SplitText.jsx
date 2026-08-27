/**
 * SplitText — splits a string into per-character animated spans.
 *
 * Each non-whitespace character is wrapped in two nested spans:
 *   <span class="charMask">          ← overflow:hidden — line-height tall mask
 *     <span class="charInner">X</span> ← slides up from translateY(100%) to 0
 *   </span>
 *
 * The outer component sets an inline `animationDelay` on every charInner so
 * left characters start their reveal earlier than right ones — this produces
 * the diagonal "wave" reveal you see on studionamma.com (Playground block).
 *
 * Words are NEVER split between lines (each word is rendered as a non-breaking
 * cluster so wrapping happens between words, not in the middle of one).
 *
 * Accessibility: the visible characters are aria-hidden; an aria-label clone
 * exposes the full text to assistive tech as a single readable string.
 */
import React from "react";

const SplitText = ({
  text,
  baseDelay = 0,
  stepMs = 22,
  charClass,
  innerClass,
  // Render the whole thing in one element so callers can attach className/style
  as: Tag = "span",
  className = "",
  style,
}) => {
  const str = String(text ?? "");
  // Split into words, preserving them as atomic wrap units.
  const words = str.split(/(\s+)/); // keeps the spaces as separate tokens
  let charIndex = 0;

  return (
    <Tag
      className={className}
      style={style}
      aria-label={str}
    >
      {words.map((token, wi) => {
        if (/^\s+$/.test(token)) {
          // Render whitespace as a normal space so layout/wrapping is preserved
          return (
            <span key={`s-${wi}`} aria-hidden="true">
              {token}
            </span>
          );
        }
        // Build a word wrapper that keeps letters together (no mid-word wraps)
        const chars = [...token];
        return (
          <span
            key={`w-${wi}`}
            aria-hidden="true"
            style={{ display: "inline-block", whiteSpace: "nowrap" }}
          >
            {chars.map((ch, ci) => {
              const delay = baseDelay + charIndex * stepMs;
              charIndex += 1;
              return (
                <span key={`c-${wi}-${ci}`} className={charClass}>
                  <span
                    className={innerClass}
                    style={{ animationDelay: `${delay}ms` }}
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

export default SplitText;
