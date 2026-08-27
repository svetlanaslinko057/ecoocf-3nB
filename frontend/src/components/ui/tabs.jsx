/**
 * shadcn/ui Tabs — patched to the platform's canonical PageTabs spec
 * (matches Executive Center / SectionTabs). Every page that imports
 * `{ Tabs, TabsList, TabsTrigger, TabsContent }` automatically inherits
 * the unified look, no manual refactor required.
 *
 * Design contract (mirror of <SectionTabs>):
 *   • TabsList:    bg white + 1px #E4E4E7 border, rounded-2xl, p-1, gap-1.
 *   • TabsTrigger: rounded-xl, transparent by default, on active gets a
 *                  solid black background (#18181B) + white text + semibold.
 *                  No outline, no shadow ring — pure filled pill.
 */
import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";

import { cn } from "@/lib/utils";

// Tabs Root is width-constrained by default (min-w-0 + max-w-full) so that a
// long TabsList inside a flex/grid parent scrolls HORIZONTALLY within itself
// instead of pushing the whole page wider on mobile.
const Tabs = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Root ref={ref} className={cn("min-w-0 max-w-full", className)} {...props} />
));
Tabs.displayName = TabsPrimitive.Root.displayName;

const TabsList = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      "inline-flex items-center justify-start gap-1 p-1 rounded-2xl bg-white border border-[#E4E4E7] text-[#52525B] max-w-full overflow-x-auto",
      className,
    )}
    style={{ scrollbarWidth: "none" }}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      // base
      "inline-flex items-center justify-center gap-2 whitespace-nowrap shrink-0 rounded-xl px-3.5 py-1.5 text-[12.5px] sm:text-[13px] font-medium transition-colors",
      "ring-offset-background focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-black/10",
      "disabled:pointer-events-none disabled:opacity-50",
      // idle
      "text-[#52525B] hover:bg-[#FAFAFA] hover:text-[#18181B]",
      // active — fully filled black pill + white text (Executive Center spec)
      "data-[state=active]:bg-[#18181B] data-[state=active]:text-white data-[state=active]:font-semibold",
      "data-[state=active]:hover:bg-black",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "mt-4 ring-offset-background focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-black/10",
      className,
    )}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
