import { Skeleton } from "@/components/ui/skeleton";
import { StatsGridSkeleton } from "@/components/ui/page-skeletons";
import { Card, CardContent } from "@/components/ui/card";

export default function AnalyticsLoading() {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <Skeleton className="h-7 w-32" />
        <Skeleton className="h-4 w-56" />
      </div>
      <StatsGridSkeleton count={4} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-5">
            <Skeleton className="h-48 w-full" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-5">
            <Skeleton className="h-48 w-full" />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
