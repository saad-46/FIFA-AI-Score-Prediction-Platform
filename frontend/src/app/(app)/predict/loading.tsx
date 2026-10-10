import { Skeleton } from "@/components/ui/skeleton";

export default function PredictLoading() {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <Skeleton className="h-7 w-64" />
        <Skeleton className="h-4 w-80" />
      </div>
      {/* Same shape as the fixture form, so nothing jumps when it arrives. */}
      <div className="space-y-5 rounded-lg border border-border bg-surface p-5">
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
        <Skeleton className="h-20 w-full" />
        <Skeleton className="ml-auto h-11 w-40" />
      </div>
    </div>
  );
}
