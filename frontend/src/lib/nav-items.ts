import {
  Activity,
  Home,
  BarChart3,
  Brain,
  Trophy,
  Users,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

/**
 * Single source of truth for primary navigation — shared by the navbar
 * (desktop + mobile) and the command palette so the two never drift.
 *
 * These are the public product. /dashboard belongs here: it is genuinely
 * public now — GET /analytics/dashboard returns the global totals to everyone
 * and simply zeroes the per-user block for anonymous callers.
 *
 * /saved and /profile are deliberately absent. Both are reachable and render
 * honest guest states rather than redirecting, but they are account features
 * with nothing to show a visitor; listing them in primary nav would push an
 * account the product does not require. They remain available by URL and via
 * the account menu once signed in.
 */
export const navItems: NavItem[] = [
  { href: "/dashboard", label: "Intelligence", icon: Home },
  { href: "/tournaments", label: "Tournament", icon: Trophy },
  { href: "/predict", label: "Simulation", icon: Brain },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/matches", label: "Matches", icon: Activity },
  { href: "/analytics", label: "Insights", icon: BarChart3 },
];
