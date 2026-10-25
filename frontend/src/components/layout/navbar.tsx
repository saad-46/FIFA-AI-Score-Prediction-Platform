"use client";

import { BrandLink } from "@/components/layout/brand-link";
import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { Menu, X, LogOut, User, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { CommandPalette } from "@/components/ui/command-palette";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { navItems } from "@/lib/nav-items";

interface NavbarProps {
  user?: { email: string; full_name?: string } | null;
}

export function Navbar({ user }: NavbarProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const reduceMotion = useReducedMotion();
  const signOutFormRef = React.useRef<HTMLFormElement>(null);

  // Glass gets heavier once the page moves under it, so the bar separates from
  // content while scrolling but stays light at rest. Passive listener, and only
  // a boolean is tracked, so this never re-renders per pixel.
  React.useEffect(() => {
    if (!mobileOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileOpen]);

  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        // A full-width bar pinned to the top edge. The floating glass pill it
        // replaces spent blur and shadow on chrome; this one only gains a
        // hairline and a solid backdrop once content scrolls beneath it.
        "sticky top-0 z-50 w-full border-b transition-colors duration-200",
        scrolled || mobileOpen
          ? "border-border bg-background/95 backdrop-blur-md"
          : "border-transparent bg-background/60 backdrop-blur-sm"
      )}
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          {/* Logo */}
          <BrandLink label="FIFA 26 Intelligence — home" className="flex shrink-0 items-center gap-2.5 rounded">
            {/* Centre circle and halfway line: the one mark every pitch shares. */}
            <svg className="h-7 w-7 text-primary" viewBox="0 0 28 28" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
              <rect x="1.5" y="4.5" width="25" height="19" rx="2.5" />
              <path d="M14 4.5v19" />
              <circle cx="14" cy="14" r="4.25" />
            </svg>
            <span className="font-display text-xl font-bold uppercase leading-none tracking-wider text-foreground">
              FIFA 26 <span className="text-primary">Intelligence</span>
            </span>
          </BrandLink>

          {/* Desktop nav */}
          {/* lg:, not md: — six items plus the search and theme controls need
              ~900px. From 768px they overflowed the header and gave the whole
              page a horizontal scrollbar. */}
          <nav aria-label="Primary" className="hidden h-full items-stretch gap-1 lg:flex">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex items-center gap-1.5 px-3 text-sm font-medium transition-colors duration-150",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                    // Active is an underline on the bar's bottom edge plus a
                    // weight and colour change: not colour alone, and
                    // aria-current carries it for assistive tech.
                    active
                      ? "font-semibold text-foreground after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:bg-primary"
                      : "text-fg-muted hover:text-foreground"
                  )}
                >
                  <Icon className={cn("h-4 w-4", active && "text-primary")} aria-hidden="true" />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* Right side */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="hidden font-normal text-fg-muted lg:inline-flex"
              onClick={() => setPaletteOpen(true)}
              aria-label="Search pages"
              aria-keyshortcuts="Control+K Meta+K"
            >
              <Search className="h-3.5 w-3.5" />
              <span className="hidden xl:inline">Search</span>
              <kbd className="ml-1 hidden rounded border border-border px-1.5 font-code text-[10px] xl:inline">Ctrl K</kbd>
            </Button>
            <ThemeToggle />
            {user ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="hidden lg:flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-foreground hover:bg-surface-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                    <Avatar className="h-7 w-7">
                      <AvatarFallback>
                        {(user.full_name || user.email)[0].toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                    <span className="max-w-[120px] truncate">
                      {user.full_name || user.email}
                    </span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem asChild>
                    <Link href="/profile" className="flex items-center gap-2 cursor-pointer">
                      <User className="h-4 w-4" />
                      Profile
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-loss focus:text-loss cursor-pointer"
                    onSelect={() => signOutFormRef.current?.requestSubmit()}
                  >
                    <LogOut className="h-4 w-4" />
                    Sign out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : null}
            {/* No sign-in / sign-up prompts: the site is fully browsable
                anonymously. The account menu above still renders for anyone
                with an existing session — auth infrastructure is intact, it
                just isn't advertised. Feedback is collected without an
                account instead (see FeedbackWidget in the footer). */}

            {/* Mobile menu toggle */}
            <button
              className="flex h-11 w-11 items-center justify-center rounded-md text-fg-muted transition-colors hover:bg-surface-2 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileOpen}
              aria-controls="mobile-nav"
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {/* Mobile menu lives inside the glass container so the bar stays one
            floating surface when it expands, rather than dropping a separate
            opaque panel underneath it. */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, height: 0 }}
              className="overflow-hidden lg:hidden"
            >
              <nav id="mobile-nav" aria-label="Primary" className="flex flex-col gap-1 border-t border-border py-3">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const active = pathname.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex min-h-11 items-center gap-3 rounded-md border-l-2 px-3 text-sm font-medium transition-colors",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        active
                          ? "border-primary bg-surface-2 font-semibold text-foreground"
                          : "border-transparent text-fg-muted hover:bg-surface-2 hover:text-foreground"
                      )}
                    >
                      <Icon className="h-4 w-4" aria-hidden="true" />
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <CommandPalette items={navItems} open={paletteOpen} onOpenChange={setPaletteOpen} />

      {/* Submitted imperatively by the "Sign out" menu item — kept outside the
          DropdownMenuItem so Radix can focus the item itself, not a form. */}
      <form ref={signOutFormRef} action="/auth/signout" method="post" className="hidden" />
    </header>
  );
}
