"use client";

import * as React from "react";
import { Check, ChevronsUpDown, Loader2, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export interface ComboboxOption {
  value: string;
  label: string;
  description?: string;
}

interface ComboboxProps {
  options: ComboboxOption[];
  value?: string;
  onValueChange: (value: string) => void;
  onSearchChange?: (query: string) => void;
  /** Overrides the trigger's displayed label — needed when `options` is a
   * transient async search-result list that may no longer contain the
   * currently-selected value once the query is cleared. */
  selectedLabel?: string;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  loading?: boolean;
  disabled?: boolean;
  className?: string;
  id?: string;
  "aria-label"?: string;
}

/**
 * Accessible search-and-select combobox (listbox + combobox ARIA pattern,
 * full keyboard nav) built on Popover rather than a native <select> since
 * options need free-text filtering. Replaces hand-rolled dropdown-div
 * patterns that had no keyboard support or ARIA roles.
 */
export function Combobox({
  options,
  value,
  onValueChange,
  onSearchChange,
  selectedLabel,
  placeholder = "Select…",
  searchPlaceholder = "Search…",
  emptyMessage = "No results found.",
  loading = false,
  disabled = false,
  className,
  id,
  "aria-label": ariaLabel,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [highlighted, setHighlighted] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const selected = options.find((o) => o.value === value);
  const displayLabel = selectedLabel ?? selected?.label;
  const listboxId = `${id ?? "combobox"}-listbox`;

  const handleQueryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.value;
    setQuery(next);
    setHighlighted(0);
    onSearchChange?.(next);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const option = options[highlighted];
      if (option) {
        onValueChange(option.value);
        setOpen(false);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          requestAnimationFrame(() => inputRef.current?.focus());
        } else {
          setQuery("");
        }
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          id={id}
          disabled={disabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          className={cn(
            "flex h-9 w-full items-center justify-between rounded-lg border border-border bg-surface-2/50 px-3 text-sm text-foreground shadow-sm transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-50",
            className
          )}
        >
          <span className={cn("truncate", !displayLabel && "text-fg-muted")}>
            {displayLabel ?? placeholder}
          </span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="h-3.5 w-3.5 shrink-0 text-fg-muted" aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={handleQueryChange}
            onKeyDown={handleKeyDown}
            placeholder={searchPlaceholder}
            role="combobox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-label={ariaLabel ?? searchPlaceholder}
            aria-activedescendant={
              options[highlighted] ? `${listboxId}-${options[highlighted].value}` : undefined
            }
            className="flex h-9 w-full bg-transparent text-sm text-foreground placeholder:text-fg-muted outline-none"
          />
          {loading && <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-fg-muted" aria-hidden="true" />}
        </div>
        <ul id={listboxId} role="listbox" aria-label={ariaLabel} className="max-h-60 overflow-y-auto p-1">
          {options.length === 0 ? (
            <li className="px-3 py-6 text-center text-sm text-fg-muted">{emptyMessage}</li>
          ) : (
            options.map((option, i) => (
              <li
                key={option.value}
                id={`${listboxId}-${option.value}`}
                role="option"
                aria-selected={option.value === value}
                onMouseEnter={() => setHighlighted(i)}
                onClick={() => {
                  onValueChange(option.value);
                  setOpen(false);
                }}
                className={cn(
                  "flex cursor-pointer items-center justify-between gap-2 rounded-md px-2 py-1.5 text-sm text-foreground",
                  i === highlighted && "bg-surface-2"
                )}
              >
                <span className="flex flex-col overflow-hidden">
                  <span className="truncate font-medium">{option.label}</span>
                  {option.description && (
                    <span className="truncate text-xs text-fg-muted">{option.description}</span>
                  )}
                </span>
                {option.value === value && <Check className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />}
              </li>
            ))
          )}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
