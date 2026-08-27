/**
 * HelpTooltip — wrap any element with a multilingual on-hover tooltip.
 *
 * Usage:
 *   <HelpTooltip text={t('tip_w14_kpi_revenue_mtd')}>
 *     <KpiTile ... />
 *   </HelpTooltip>
 *
 * Differs from the raw shadcn/Radix tooltip in three ways:
 *   1. Self-contained — it provides its own TooltipProvider, so it can be
 *      dropped into any page without wiring at the root.
 *   2. No-op fallback when `text` is empty/undefined — the children are
 *      rendered as-is. This keeps the call sites tidy when translation
 *      keys are still pending.
 *   3. Touch-device friendly — falls back to native `title` attribute
 *      when matchMedia indicates a coarse pointer (mobile/tablet).
 *
 * Designed for Wave 12A/12C/13/14/15/16/17/18/19 admin pages.
 */
import * as React from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./tooltip";

const useIsCoarsePointer = () => {
  const [coarse, setCoarse] = React.useState(false);
  React.useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia("(pointer: coarse)");
    const update = () => setCoarse(mql.matches);
    update();
    try {
      mql.addEventListener("change", update);
      return () => mql.removeEventListener("change", update);
    } catch {
      mql.addListener(update);
      return () => mql.removeListener(update);
    }
  }, []);
  return coarse;
};

const HelpTooltip = ({
  text,
  children,
  side = "top",
  align = "center",
  delayDuration = 200,
  asChild = true,
  className,
  contentClassName,
}) => {
  const coarse = useIsCoarsePointer();

  if (!text || typeof text !== "string" || text.trim() === "") {
    return <>{children}</>;
  }

  // On touch devices (no native hover), Radix tooltip becomes intrusive
  // (needs long-press). Use native `title` for accessibility instead.
  if (coarse) {
    // Native `title` works on a wrapper span — keeps children intact.
    return (
      <span title={text} className={className} style={{ display: "contents" }}>
        {children}
      </span>
    );
  }

  return (
    <TooltipProvider delayDuration={delayDuration} disableHoverableContent>
      <Tooltip>
        <TooltipTrigger asChild={asChild}>
          {asChild ? (
            children
          ) : (
            <span className={className} style={{ display: "inline-flex" }}>
              {children}
            </span>
          )}
        </TooltipTrigger>
        <TooltipContent
          side={side}
          align={align}
          className={
            "max-w-xs whitespace-normal text-[12px] leading-snug font-normal " +
            "bg-[#18181B] text-white border border-[#27272A] shadow-lg " +
            "px-3 py-2 rounded-lg z-[60] " +
            (contentClassName || "")
          }
        >
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default HelpTooltip;
export { HelpTooltip };
