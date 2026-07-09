"use client";

import useSWR from "swr";
import { Trophy } from "lucide-react";
import { tournamentApi } from "@/lib/api/tournament";
import { getApiErrorMessage } from "@/lib/api/client";
import { GroupCard } from "@/components/football/group-card";
import { CardGridSkeleton } from "@/components/ui/page-skeletons";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";

export function GroupsView() {
  const { data: groups, error, isLoading, mutate } = useSWR("tournament-groups", tournamentApi.getGroups);

  if (isLoading) return <CardGridSkeleton count={12} />;

  if (error) {
    return (
      <ErrorState
        title="Couldn't load the groups"
        description={getApiErrorMessage(error)}
        onRetry={() => mutate()}
      />
    );
  }

  const entries = groups?.groups ?? [];
  if (entries.length === 0) {
    return <EmptyState icon={Trophy} title="Groups not available yet" />;
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[...entries]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((group) => (
          <GroupCard key={group.name} groupLetter={group.name} teams={group.teams} />
        ))}
    </div>
  );
}
