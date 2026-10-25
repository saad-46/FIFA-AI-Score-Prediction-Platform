"use client";

import useSWR from "swr";
import { wc2026Api } from "@/lib/api/wc2026";
import { Skeleton } from "@/components/ui/skeleton";
import { FinalHero } from "@/components/dashboard/dashboard-view";

/**
 * The real final on the landing page, from the same endpoint the overview uses.
 *
 * If the request fails the block is simply absent: the landing page is an
 * introduction, and a red error panel as its centrepiece would say less about
 * the product than leaving the space out. The tournament page itself reports
 * the failure properly.
 */
export function LandingFinal() {
  const { data, error, isLoading } = useSWR("wc2026-bracket", wc2026Api.getBracket);
  if (isLoading) return <Skeleton className="h-72 w-full rounded-lg" />;
  if (error || !data) return null;

  const final = data.nodes.find((n) => n.stage === "final");
  if (!final) return null;
  return <FinalHero final={final} />;
}
