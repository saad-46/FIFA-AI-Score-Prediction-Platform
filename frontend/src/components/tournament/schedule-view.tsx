"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { CalendarDays } from "lucide-react";
import { tournamentApi } from "@/lib/api/tournament";
import { getApiErrorMessage } from "@/lib/api/client";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { ListSkeleton } from "@/components/ui/page-skeletons";
import { formatDate } from "@/lib/utils";
import { getCountryFlag } from "@/components/football/team-identity";

export function ScheduleView() {
  const { data: schedule, error, isLoading, mutate } = useSWR("tournament-schedule", () =>
    tournamentApi.getSchedule()
  );
  const [stageFilter, setStageFilter] = useState("all");

  const matches = useMemo(() => schedule?.matches ?? [], [schedule]);

  const stages = useMemo(() => Array.from(new Set(matches.map((m) => m.stage))).sort(), [matches]);

  const filtered = useMemo(
    () => (stageFilter === "all" ? matches : matches.filter((m) => m.stage === stageFilter)),
    [matches, stageFilter]
  );

  if (isLoading) return <ListSkeleton count={10} />;

  if (error) {
    return (
      <ErrorState
        title="Couldn't load the schedule"
        description={getApiErrorMessage(error)}
        onRetry={() => mutate()}
      />
    );
  }

  if (matches.length === 0) {
    return <EmptyState icon={CalendarDays} title="Schedule not available yet" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Select value={stageFilter} onValueChange={setStageFilter}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Filter by stage" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All stages</SelectItem>
            {stages.map((stage) => (
              <SelectItem key={stage} value={stage}>
                {stage}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-sm text-fg-muted">{filtered.length} fixtures</p>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>Fixture</TableHead>
            <TableHead>Stage</TableHead>
            <TableHead>Venue</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((m) => (
            <TableRow key={m.match_number}>
              <TableCell className="whitespace-nowrap text-fg-muted">
                {formatDate(m.date)}
                <span className="ml-1.5 text-xs">{m.kickoff_time_et} ET</span>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2.5 font-mono text-sm">
                  <div className="flex items-center gap-1.5 min-w-[70px] justify-end">
                    <span className={m.home_team.length > 3 ? "text-fg-muted" : "font-semibold"}>
                      {m.home_team}
                    </span>
                    <span className="text-base select-none shrink-0" aria-hidden="true">
                      {m.home_team.length === 3 ? getCountryFlag("", m.home_team) : "⚽"}
                    </span>
                  </div>
                  <span className="text-fg-muted/40 font-normal text-xs">vs</span>
                  <div className="flex items-center gap-1.5 min-w-[70px] justify-start">
                    <span className="text-base select-none shrink-0" aria-hidden="true">
                      {m.away_team.length === 3 ? getCountryFlag("", m.away_team) : "⚽"}
                    </span>
                    <span className={m.away_team.length > 3 ? "text-fg-muted" : "font-semibold"}>
                      {m.away_team}
                    </span>
                  </div>
                  {m.uncertain && (
                    <Badge variant="outline" className="text-[10px] font-mono tracking-wider px-1">
                      TBD
                    </Badge>
                  )}
                </div>
              </TableCell>
              <TableCell>
                {m.group ? `Group ${m.group}` : m.stage}
              </TableCell>
              <TableCell className="text-fg-muted">{m.venue_city}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
