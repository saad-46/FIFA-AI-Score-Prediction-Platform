import { Skeleton } from "@/components/ui/skeleton";
import { ListSkeleton } from "@/components/ui/page-skeletons";

export default function MatchesLoading() {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <Skeleton className="h-7 w-32" />
        <Skeleton className="h-4 w-48" />
      </div>
      <ListSkeleton count={8} />
    </div>
  );
}
