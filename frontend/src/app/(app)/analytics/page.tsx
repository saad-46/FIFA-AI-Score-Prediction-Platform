import type { Metadata } from "next";
import { AnalyticsView } from "@/components/analytics/analytics-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = {
  title: "Analytics",
  description: "Goals, results and scorelines across the World Cup match record, and how the model's predictions scored.",
};

export default function AnalyticsPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Analytics"
        description="How World Cup matches have gone: goals, results and scorelines across the match record, and how the model's predictions scored."
      />
      <AnalyticsView />
    </div>
  );
}
