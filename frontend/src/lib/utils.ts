import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(date));
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatGoals(value: number): string {
  return value.toFixed(2);
}

export function getResultColor(result: "W" | "D" | "L"): string {
  switch (result) {
    case "W":
      return "text-emerald-400";
    case "D":
      return "text-amber-400";
    case "L":
      return "text-red-400";
  }
}

export function getResultBg(result: "W" | "D" | "L"): string {
  switch (result) {
    case "W":
      return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
    case "D":
      return "bg-amber-500/20 text-amber-400 border-amber-500/30";
    case "L":
      return "bg-red-500/20 text-red-400 border-red-500/30";
  }
}

export function getProbabilityColor(prob: number): string {
  if (prob >= 0.6) return "text-emerald-400";
  if (prob >= 0.4) return "text-amber-400";
  return "text-red-400";
}
