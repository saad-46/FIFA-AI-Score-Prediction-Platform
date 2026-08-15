"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import useSWRMutation from "swr/mutation";
import { Play } from "lucide-react";
import { tournamentApi } from "@/lib/api/tournament";
import { getApiErrorMessage } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { SimulationProgress } from "@/components/football/simulation-progress";
import { StageProbabilityTable } from "@/components/football/stage-probability-table";
import { ErrorState } from "@/components/ui/error-state";
import { toast } from "@/hooks/use-toast";

const SIM_OPTIONS = [1000, 5000, 10000, 25000, 50000, 100000];

export function SimulateView() {
  const [nSimulations, setNSimulations] = useState(10000);
  const [useRealResults, setUseRealResults] = useState(true);

  const { data: groups } = useSWR("tournament-groups", tournamentApi.getGroups);
  const teamNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const group of groups?.groups ?? []) {
      for (const t of group.teams) map[t.code] = t.name;
    }
    return map;
  }, [groups]);

  const { trigger, data, error, isMutating } = useSWRMutation(
    "tournament-simulate",
    (_key: string, { arg }: { arg: { n_simulations: number; use_real_results: boolean } }) =>
      tournamentApi.simulate({
        use_fifa_2026_groups: true,
        n_simulations: arg.n_simulations,
        use_real_results: arg.use_real_results,
      })
  );

  const handleRun = async () => {
    try {
      await trigger({ n_simulations: nSimulations, use_real_results: useRealResults });
    } catch (err) {
      toast({ title: "Simulation failed", description: getApiErrorMessage(err), variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Run a simulation</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-wrap items-end gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="n_simulations">Simulations</Label>
              <Select value={String(nSimulations)} onValueChange={(v) => setNSimulations(Number(v))}>
                <SelectTrigger id="n_simulations" className="w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SIM_OPTIONS.map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      {n.toLocaleString()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2 pb-2">
              <Switch id="use_real_results" checked={useRealResults} onCheckedChange={setUseRealResults} />
              <Label htmlFor="use_real_results" className="cursor-pointer">
                Use real 2026 results
              </Label>
            </div>
          </div>
          {/* Without this, the tab reads as a contradiction: the Bracket tab
              shows 2026 finished with Spain champion, while this table gives
              Spain ~2%. Both are right. Each run redraws the knockout from
              simulated group tables, so a pairing only takes a real score when
              it happens to match a fixture that was actually played — most
              simulated brackets never reproduce the real ones. The switch
              suppresses re-simulating known facts; it does not replay the
              tournament. Say so rather than letting the numbers look broken. */}
          <Button variant="gradient" onClick={handleRun} loading={isMutating}>
            {!isMutating && <Play className="h-4 w-4" />}
            {isMutating ? "Simulating…" : "Run simulation"}
          </Button>
        </CardContent>
        <CardContent className="pt-0">
          <p className="text-xs leading-relaxed text-fg-muted">
            Every run redraws the knockout stage from simulated group tables, so these are
            probabilities across {nSimulations.toLocaleString()} hypothetical tournaments — not a
            replay of the real one. With the switch on, a tie only takes its real score when the
            simulated draw happens to reproduce a fixture that was actually played; everything else
            is genuinely simulated. The completed 2026 tournament is on the Bracket tab.
          </p>
        </CardContent>
      </Card>

      {isMutating && <SimulationProgress simulations={nSimulations} />}

      {error && !isMutating && (
        <ErrorState title="Simulation failed" description={getApiErrorMessage(error)} onRetry={handleRun} />
      )}

      {data && !isMutating && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>Results</CardTitle>
          </CardHeader>
          <CardContent>
            <StageProbabilityTable probabilities={data.probabilities} teamNames={teamNames} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
