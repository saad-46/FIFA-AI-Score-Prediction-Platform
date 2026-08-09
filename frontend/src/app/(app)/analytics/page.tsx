import type { Metadata } from "next";
import { BarChart3 } from "lucide-react";
import { AnalyticsView } from "@/components/analytics/analytics-view";

export const metadata: Metadata = {
  title: "Insights",
  description: "Historical match data, model performance, and prediction insights.",
};

export default function AnalyticsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-foreground font-mono uppercase">
          <BarChart3 className="h-6 w-6 text-primary" aria-hidden="true" />
          Insights
        </h1>
        <p className="mt-1 text-sm text-fg-muted">Historical performance distributions and ML validation statistics</p>
      </div>
      <AnalyticsView />
    </div>
  );
}
