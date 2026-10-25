"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { MouseEvent, ReactNode } from "react";
import { setSkipped } from "@/components/intro/intro-state";

/**
 * The FIFA 26 Intelligence mark: a real link to the landing page that also re-enters its scroll-driven intro.
 *
 * Plain clicks are handled here; anything else (middle click, ctrl/cmd-click, "open in new tab") is left to the
 * browser so the link still behaves like a link. Clicking marks the intro as not skipped, so a visitor who
 * skipped it earlier gets it again, then either routes to "/" (the page opens at the top, where the intro starts)
 * or, when already there, scrolls back to the top. Close to the top that scroll is smooth; from far down the page
 * it jumps, so the visitor is not made to wait through a long animated scroll. With reduced motion it always jumps.
 */
export function BrandLink({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const onClick = (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    setSkipped(false);
    if (pathname === "/") {
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const near = window.scrollY < window.innerHeight * 3;
      window.scrollTo({ top: 0, behavior: reduced || !near ? "instant" : "smooth" });
    } else {
      router.push("/");
    }
  };

  return (
    <Link
      href="/"
      onClick={onClick}
      aria-label={label}
      className={className}
    >
      {children}
    </Link>
  );
}
