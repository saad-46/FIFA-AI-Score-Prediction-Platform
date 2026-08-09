import {
  Activity,
  BarChart3,
  BookmarkCheck,
  Brain,
  Home,
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
export const navItems: NavItem[] = [
  { href: "/dashboard", label: "Intelligence", icon: Home },
  { href: "/predict", label: "Simulation", icon: Brain },
  { href: "/analytics", label: "Insights", icon: BarChart3 },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/matches", label: "Matches", icon: Activity },
  { href: "/tournaments", label: "Tournament Intelligence", icon: Trophy },
  { href: "/saved", label: "Saved", icon: BookmarkCheck },
];
