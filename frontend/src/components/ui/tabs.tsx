"use client";

import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

const Tabs = TabsPrimitive.Root;

/**
 * The tab strip.
 *
 * It is its own horizontal scroller (`overflow-x-auto`, not `overflow-hidden`):
 * on a phone the labels together are wider than the screen, and a strip that
 * only clips leaves the last tabs unreachable. Native touch scrolling moves it,
 * and keyboard arrows move focus along it -- the browser scrolls a focused tab
 * into view. The one thing the browser does not do is bring a tab into view
 * when the selection changes some other way (a `?tab=` link, for example), so
 * that is handled below.
 */
const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, forwardedRef) => {
  const inner = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const list = inner.current;
    if (!list) return;
    const reveal = () => {
      const active = list.querySelector<HTMLElement>('[role="tab"][data-state="active"]');
      if (!active) return;
      // Scroll the strip itself, never the page.
      const left = active.offsetLeft - (list.clientWidth - active.offsetWidth) / 2;
      list.scrollTo({ left: Math.max(0, left), behavior: "auto" });
    };
    reveal();
    const observer = new MutationObserver(reveal);
    observer.observe(list, { subtree: true, attributes: true, attributeFilter: ["data-state"] });
    return () => observer.disconnect();
  }, []);

  return (
    <TabsPrimitive.List
      ref={(node) => {
        inner.current = node;
        if (typeof forwardedRef === "function") forwardedRef(node);
        else if (forwardedRef) (forwardedRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
      }}
      className={cn(
        "relative flex h-11 w-full items-stretch gap-1 overflow-x-auto overscroll-x-contain border-b border-border text-fg-muted",
        // The scrollbar is hidden (the cut-off tab at the edge is the cue and
        // touch is the control) but keyboard focus still scrolls the strip.
        "[scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className
      )}
      {...props}
    />
  );
});
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "relative inline-flex shrink-0 items-center justify-center whitespace-nowrap border-b-2 border-transparent px-3 text-sm font-medium transition-colors",
      "hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
      "disabled:pointer-events-none disabled:opacity-50",
      // Selected: weight, colour and a rule -- three cues, not colour alone.
      "data-[state=active]:border-primary data-[state=active]:font-semibold data-[state=active]:text-foreground",
      className
    )}
    {...props}
  />
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "mt-6 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
      className
    )}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
