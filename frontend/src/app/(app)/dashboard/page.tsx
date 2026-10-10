import type { Metadata } from "next";
import { DashboardView } from "@/components/dashboard/dashboard-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Overview" };

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="FIFA World Cup 2026"
        title="Overview"
        description="The finished tournament at a glance, with the match predictor and tournament simulator one step away."
      />
      <DashboardView />
    </div>
  );
}
