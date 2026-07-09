import { Skeleton } from "@/components/ui/skeleton";
import { StatsGridSkeleton, CardGridSkeleton } from "@/components/ui/page-skeletons";

export default function DashboardLoading() {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <Skeleton className="h-7 w-40" />
        <Skeleton className="h-4 w-56" />
      </div>
      <StatsGridSkeleton count={4} />
      <CardGridSkeleton count={3} />
    </div>
  );
}
