"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GroupsView } from "@/components/tournament/groups-view";
import { ScheduleView } from "@/components/tournament/schedule-view";
import { SimulateView } from "@/components/tournament/simulate-view";

export function TournamentTabs() {
  return (
    <Tabs defaultValue="groups">
      <TabsList>
        <TabsTrigger value="groups">Groups</TabsTrigger>
        <TabsTrigger value="schedule">Schedule</TabsTrigger>
        <TabsTrigger value="simulator">Simulator</TabsTrigger>
      </TabsList>
      <TabsContent value="groups">
        <GroupsView />
      </TabsContent>
      <TabsContent value="schedule">
        <ScheduleView />
      </TabsContent>
      <TabsContent value="simulator">
        <SimulateView />
      </TabsContent>
    </Tabs>
  );
}
