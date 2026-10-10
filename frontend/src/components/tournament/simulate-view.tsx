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
import type { TournamentSimulationMeta } from "@/types";

const SIM_OPTIONS = [1000, 5000, 10000, 25000, 50000, 100000];

/** Headline for a result, chosen from what the server says it simulated —
 * never from what the client asked for. */
const MODE_TITLES: Record<string, string> = {
  pre_tournament: "Pre-tournament forecast",
  after_group_stage: "Knockout forecast after the real group stage",
  custom_groups: "Hypothetical tournament",
  legacy: "Simulation results",
};

function formatDate(iso: string | null | undefined) {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

function SimulationProvenance({ meta }: { meta: TournamentSimulationMeta }) {
  const through = formatDate(meta.data_through);
  const se = meta.max_champion_standard_error;
  return (
    <div className="space-y-2 border-b border-border/60 pb-4">
      {meta.note && <p className="text-sm leading-relaxed text-fg-muted">{meta.note}</p>}
      <dl className="flex flex-wrap gap-x-6 gap-y-1 font-mono text-[11px] uppercase tracking-wider text-zinc-500">
        <div className="flex gap-1.5">
          <dt>Model</dt>
          <dd className="normal-case tracking-normal text-fg-muted">{meta.model_version}</dd>
        </div>
        {through && (
          <div className="flex gap-1.5">
            <dt>Uses matches through</dt>
            <dd className="normal-case tracking-normal text-fg-muted">{through}</dd>
          </div>
        )}
        <div className="flex gap-1.5">
          <dt>Simulations</dt>
          <dd className="normal-case tracking-normal text-fg-muted">{meta.n_simulations.toLocaleString()}</dd>
        </div>
        {typeof se === "number" && (
          <div className="flex gap-1.5">
            <dt>Sampling error</dt>
            <dd className="normal-case tracking-normal text-fg-muted">
              up to ±{(se * 196).toFixed(1)} pts on a title chance
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}

export function SimulateView() {
  const [nSimulations, setNSimulations] = useState(10000);
  // What "real results" means depends on the engine the server runs, which
  // the client only learns from a response's `meta`. So the control keeps a
  // label that is true for both, and the result card states exactly what was
  // simulated.
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

  const meta = data?.meta ?? null;
  const title = meta ? MODE_TITLES[meta.mode] ?? "Simulation results" : "Simulation results";

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
          <Button variant="gradient" onClick={handleRun} loading={isMutating}>
            {!isMutating && <Play className="h-4 w-4" />}
            {isMutating ? "Simulating…" : "Run simulation"}
          </Button>
        </CardContent>
        {/* The 2026 World Cup is over, so this tab cannot be a prediction of
            it. Only what holds for every engine is said here; the result card
            carries the server's own description of what it simulated. */}
        <CardContent className="pt-0">
          <p className="text-xs leading-relaxed text-fg-muted">
            The 2026 World Cup has been played; real results are on the Bracket tab. These are chances
            across {nSimulations.toLocaleString()} simulated tournaments, not a replay — a team that won
            the real thing can show a modest chance here. With the switch off, nothing from the real
            tournament is used; each result states exactly what was simulated and from which data.
          </p>
        </CardContent>
      </Card>

      {isMutating && (
        <SimulationProgress simulations={nSimulations} expectedDurationMs={1500 + nSimulations / 8} />
      )}

      {error && !isMutating && (
        <ErrorState title="Simulation failed" description={getApiErrorMessage(error)} onRetry={handleRun} />
      )}

      {data && !isMutating && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>{title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {meta && <SimulationProvenance meta={meta} />}
            <StageProbabilityTable probabilities={data.probabilities} teamNames={teamNames} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
