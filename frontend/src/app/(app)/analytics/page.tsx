import type { Metadata } from "next";
import { BarChart3 } from "lucide-react";
import { AnalyticsView } from "@/components/analytics/analytics-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "Insights",
  description: "Historical match data, model performance, and prediction insights.",
};

export default function AnalyticsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        icon={BarChart3}
        title="Insights"
        description="Historical performance distributions and ML validation statistics"
      />
      <AnalyticsView />
    </div>
  );
}
