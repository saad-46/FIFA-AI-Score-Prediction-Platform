import type { Metadata } from "next";
import { BarChart3 } from "lucide-react";
import { AnalyticsView } from "@/components/analytics/analytics-view";

export const metadata: Metadata = {
  title: "Analytics",
  description: "Historical match data, model performance, and prediction analytics.",
};

export default function AnalyticsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
          <BarChart3 className="h-6 w-6 text-primary" aria-hidden="true" />
          Analytics
        </h1>
        <p className="mt-1 text-sm text-fg-muted">Historical match data and model performance</p>
      </div>
      <AnalyticsView />
    </div>
  );
}
