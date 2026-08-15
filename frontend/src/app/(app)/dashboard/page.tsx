import type { Metadata } from "next";
import Link from "next/link";
import { Brain } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DashboardView } from "@/components/dashboard/dashboard-view";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Intelligence" };

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Intelligence"
        description="Global score projections and tournament simulations"
        actions={
          <Button variant="gradient" asChild>
            <Link href="/predict">
              <Brain className="h-4 w-4" />
              New Prediction
            </Link>
          </Button>
        }
      />
      <DashboardView />
    </div>
  );
}
