import {
  Activity,
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

/** Single source of truth for primary navigation — shared by the navbar
 * (desktop + mobile) and the command palette so the two never drift. */
/**
 * Public navigation.
 *
 * Deliberately excludes /dashboard, /saved and /profile: middleware.ts still
 * protects those three, so with the sign-in UI removed an anonymous visitor
 * clicking them was redirected to /auth/login — a page nothing else links to.
 * The nav was advertising dead ends. The routes and their auth gate are
 * untouched; they simply are not offered to visitors who cannot reach them.
 */
export const navItems: NavItem[] = [
  { href: "/tournaments", label: "Tournament", icon: Trophy },
  { href: "/predict", label: "Simulation", icon: Brain },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/matches", label: "Matches", icon: Activity },
  { href: "/analytics", label: "Insights", icon: BarChart3 },
];
