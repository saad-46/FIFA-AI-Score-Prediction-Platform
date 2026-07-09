import { Skeleton } from "@/components/ui/skeleton";
import { CardGridSkeleton } from "@/components/ui/page-skeletons";

export default function TeamsLoading() {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <Skeleton className="h-7 w-32" />
        <Skeleton className="h-4 w-48" />
      </div>
      <Skeleton className="h-10 w-full max-w-sm" />
      <CardGridSkeleton count={9} />
    </div>
  );
}
