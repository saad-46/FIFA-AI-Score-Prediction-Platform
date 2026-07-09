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
      return "text-win";
    case "D":
      return "text-draw";
    case "L":
      return "text-loss";
  }
}

export function getResultBg(result: "W" | "D" | "L"): string {
  switch (result) {
    case "W":
      return "bg-win/20 text-win border-win/30";
    case "D":
      return "bg-draw/20 text-draw border-draw/30";
    case "L":
      return "bg-loss/20 text-loss border-loss/30";
  }
}

export function getProbabilityColor(prob: number): string {
  if (prob >= 0.6) return "text-win";
  if (prob >= 0.4) return "text-draw";
  return "text-loss";
}
