"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import type { NavItem } from "@/lib/nav-items";

interface CommandPaletteProps {
  items: NavItem[];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

/** Global ⌘K / Ctrl+K navigator. Open state can be externally controlled
 * (e.g. a visible "Search" button) or left uncontrolled — the keyboard
 * shortcut always works either way. */
export function CommandPalette({ items, open: openProp, onOpenChange }: CommandPaletteProps) {
  const [openState, setOpenState] = React.useState(false);
  const open = openProp ?? openState;
  const openRef = React.useRef(open);

  React.useEffect(() => {
    openRef.current = open;
  }, [open]);

  const [query, setQuery] = React.useState("");
  const [highlighted, setHighlighted] = React.useState(0);
  const router = useRouter();

  const setOpen = React.useCallback(
    (next: boolean) => {
      setOpenState(next);
      onOpenChange?.(next);
      if (!next) {
        setQuery("");
        setHighlighted(0);
      }
    },
    [onOpenChange]
  );

  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!openRef.current);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [setOpen]);

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) => item.label.toLowerCase().includes(q));
  }, [items, query]);

  const select = React.useCallback(
    (item: NavItem) => {
      setOpen(false);
      router.push(item.href);
    },
    [router, setOpen]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = filtered[highlighted];
      if (item) select(item);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg p-0 gap-0">
        {/* Radix requires a DialogTitle for the dialog to have an accessible
            name; without one it logs an error and screen readers announce an
            unnamed dialog. An aria-label on the content does not satisfy the
            labelling Radix wires up, so the title is rendered and visually
            hidden instead. */}
        <DialogTitle className="sr-only">Search and navigate</DialogTitle>
        <div className="flex items-center gap-2 border-b border-border px-4">
          <Search className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden="true" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Jump to a page…"
            role="combobox"
            aria-expanded={open}
            aria-controls="command-palette-list"
            aria-label="Search pages"
            className="flex h-12 w-full bg-transparent text-sm text-foreground placeholder:text-fg-muted outline-none"
          />
          <kbd className="hidden sm:inline-flex h-5 shrink-0 items-center rounded border border-border px-1.5 text-[10px] text-fg-muted">
            Esc
          </kbd>
        </div>
        <ul id="command-palette-list" role="listbox" aria-label="Pages" className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <li className="px-3 py-8 text-center text-sm text-fg-muted">No results found.</li>
          ) : (
            filtered.map((item, i) => {
              const Icon = item.icon;
              return (
                <li
                  key={item.href}
                  id={`command-palette-item-${i}`}
                  role="option"
                  aria-selected={i === highlighted}
                  onMouseEnter={() => setHighlighted(i)}
                  onClick={() => select(item)}
                  className={cn(
                    "flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm text-foreground",
                    i === highlighted && "bg-surface-2"
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden="true" />
                  {item.label}
                </li>
              );
            })
          )}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
