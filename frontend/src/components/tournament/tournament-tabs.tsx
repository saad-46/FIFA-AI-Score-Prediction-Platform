"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
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
const TABS = ["bracket", "standings", "groups", "schedule", "simulator", "backtest"] as const;
type TabId = (typeof TABS)[number];

export function TournamentTabs() {
  // The open tab lives in ?tab= so it survives a reload, can be linked to from
  // the overview, and the browser's back button steps through tabs.
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const requested = params.get("tab");
  const active: TabId = (TABS as readonly string[]).includes(requested ?? "") ? (requested as TabId) : "bracket";

  const onChange = useCallback(
    (value: string) => {
      const next = new URLSearchParams(params.toString());
      if (value === "bracket") next.delete("tab");
      else next.set("tab", value);
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [params, pathname, router]
  );

  return (
    <Tabs value={active} onValueChange={onChange}>
      <div>
        <TabsList aria-label="World Cup 2026 sections">
          <TabsTrigger value="bracket">Bracket</TabsTrigger>
          <TabsTrigger value="standings">Standings</TabsTrigger>
          <TabsTrigger value="groups">Groups</TabsTrigger>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
          <TabsTrigger value="simulator">Simulator</TabsTrigger>
          <TabsTrigger value="backtest">Model vs reality</TabsTrigger>
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
