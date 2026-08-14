"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GroupsView } from "@/components/tournament/groups-view";
import { ScheduleView } from "@/components/tournament/schedule-view";
import { SimulateView } from "@/components/tournament/simulate-view";
import { TournamentBracket } from "@/components/wc2026/tournament-bracket";
import { GroupStandings } from "@/components/wc2026/group-standings";
import { BacktestView } from "@/components/wc2026/backtest-view";

/**
 * The WC2026 hub.
 *
 * Bracket leads because it is the thing people come here for; the pre-existing
 * Groups / Schedule / Simulation views are kept untouched behind their own
 * tabs. "Model vs Reality" sits last — it is a retrospective, so it should not
 * compete with the tournament itself for attention.
 *
 * The tab strip scrolls horizontally on narrow screens rather than wrapping
 * into a second row, which would push the content below the fold on mobile.
 */
export function TournamentTabs() {
  return (
    <Tabs defaultValue="bracket">
      <div className="-mx-1 overflow-x-auto px-1 pb-1">
        <TabsList className="font-mono text-xs uppercase tracking-wider">
          <TabsTrigger value="bracket">Bracket</TabsTrigger>
          <TabsTrigger value="standings">Standings</TabsTrigger>
          <TabsTrigger value="groups">Groups</TabsTrigger>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
          <TabsTrigger value="simulator">Simulation Matrix</TabsTrigger>
          <TabsTrigger value="backtest">Model vs Reality</TabsTrigger>
        </TabsList>
      </div>

      <TabsContent value="bracket">
        <TournamentBracket />
      </TabsContent>
      <TabsContent value="standings">
        <GroupStandings />
      </TabsContent>
      <TabsContent value="groups">
        <GroupsView />
      </TabsContent>
      <TabsContent value="schedule">
        <ScheduleView />
      </TabsContent>
      <TabsContent value="simulator">
        <SimulateView />
      </TabsContent>
      <TabsContent value="backtest">
        <BacktestView />
      </TabsContent>
    </Tabs>
  );
}
