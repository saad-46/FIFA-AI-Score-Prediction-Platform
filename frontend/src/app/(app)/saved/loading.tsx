import { Skeleton } from "@/components/ui/skeleton";
import { ListSkeleton } from "@/components/ui/page-skeletons";

export default function SavedLoading() {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      <ListSkeleton count={5} />
    </div>
  );
}
