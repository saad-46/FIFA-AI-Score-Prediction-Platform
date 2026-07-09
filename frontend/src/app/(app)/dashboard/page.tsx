import type { Metadata } from "next";
import Link from "next/link";
import { Brain } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DashboardView } from "@/components/dashboard/dashboard-view";

export const metadata: Metadata = { title: "Dashboard" };

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
          <p className="mt-1 text-sm text-fg-muted">Your AI prediction overview</p>
        </div>
        <Button variant="gradient" asChild>
          <Link href="/predict">
            <Brain className="h-4 w-4" />
            New Prediction
          </Link>
        </Button>
      </div>
      <DashboardView />
    </div>
  );
}
