"use client";

import React, { useState } from "react";
import { Brain, ArrowRight, RefreshCw, Cpu, ShieldAlert } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Combobox } from "@/components/ui/combobox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { predictionsApi } from "@/lib/api/predictions";
import { getApiErrorMessage } from "@/lib/api/client";
import type { PredictionResult, Team } from "@/types";
import { toast } from "@/hooks/use-toast";
import { useTeamSearch } from "@/hooks/use-team-search";
import { TeamFlag } from "@/components/football/team-flag";

const schema = z.object({
  home_team: z.string().min(1, "Select a home team"),
  away_team: z.string().min(1, "Select an away team"),
  tournament: z.string().optional(),
  neutral_venue: z.boolean(),
});

type FormValues = {
  home_team: string;
  away_team: string;
  tournament?: string;
  neutral_venue: boolean;
};

const TOURNAMENTS = [
  "FIFA World Cup",
  "UEFA Euro",
  "Copa America",
  "Africa Cup of Nations",
  "AFC Asian Cup",
  "CONCACAF Gold Cup",
  "FIFA Confederations Cup",
  "Friendly",
  "UEFA Nations League",
  "CONMEBOL World Cup Qualifying",
  "UEFA World Cup Qualifying",
];

interface PredictionFormProps {
  onResult: (result: PredictionResult) => void;
  onStartPredict: () => void;
  onPredictError: () => void;
}

export function PredictionForm({ onResult, onStartPredict, onPredictError }: PredictionFormProps) {
  const [loading, setLoading] = useState(false);
  const [homeSearch, setHomeSearch] = useState("");
  const [awaySearch, setAwaySearch] = useState("");
  const { results: homeTeams, loading: homeSearching } = useTeamSearch(homeSearch);
  const { results: awayTeams, loading: awaySearching } = useTeamSearch(awaySearch);

  const [selectedHome, setSelectedHome] = useState<Team | null>(null);
  const [selectedAway, setSelectedAway] = useState<Team | null>(null);

  const {
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { neutral_venue: false },
  });

  const homeTeamValue = watch("home_team");
  const awayTeamValue = watch("away_team");
  const neutralVenue = watch("neutral_venue");
  const tournamentValue = watch("tournament");

  const onSubmit = async (values: FormValues) => {
    if (values.home_team === values.away_team) {
      toast({
        title: "Simulation Conflict",
        description: "Select two distinct teams to run the prediction model.",
        variant: "destructive",
      });
      return;
    }
    setLoading(true);
    onStartPredict();
    try {
      const result = await predictionsApi.predict(values);
      onResult(result);
    } catch (err: unknown) {
      toast({ title: "Simulation Failed", description: getApiErrorMessage(err), variant: "destructive" });
      onPredictError();
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border border-border bg-surface/40 backdrop-blur-md shadow-2xl">
      <CardHeader className="border-b border-border/40 pb-4">
        <CardTitle className="flex items-center gap-2.5 font-mono text-sm tracking-widest uppercase text-foreground">
          <Cpu className="h-4.5 w-4.5 text-primary" aria-hidden="true" />
          Simulation Parameters
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Dual Node Selectors */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 relative">
            {/* Left Node: Home */}
            <div className="space-y-4 rounded-lg border border-border/40 bg-zinc-950/20 p-4">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono tracking-widest text-zinc-500 uppercase">NODE_01 // HOME</span>
                {selectedHome && (
                  <span className="text-[10px] font-mono text-primary font-bold">
                    {selectedHome.confederation}
                  </span>
                )}
              </div>
              
              <div className="space-y-1.5">
                <Label htmlFor="home_team_combobox" className="text-xs font-mono tracking-wider text-zinc-400">Team Identifier</Label>
                <Combobox
                  id="home_team_combobox"
                  aria-label="Search for a home team"
                  value={homeTeamValue}
                  onValueChange={(v) => {
                    setValue("home_team", v, { shouldValidate: true });
                    const team = homeTeams.find((t) => t.name === v);
                    if (team) setSelectedHome(team);
                  }}
                  onSearchChange={setHomeSearch}
                  loading={homeSearching}
                  placeholder="Select home team…"
                  searchPlaceholder="Type team name…"
                  emptyMessage={homeSearch.length < 2 ? "Keep typing…" : "No matches found."}
                  options={homeTeams.map((t) => ({ value: t.name, label: t.name, description: t.country }))}
                />
                {errors.home_team && <p className="text-xs text-loss font-mono">{errors.home_team.message}</p>}
              </div>

              {/* Dynamic Preview */}
              {selectedHome && (
                <div className="pt-2 border-t border-border/20 grid grid-cols-3 gap-2 text-center">
                  <div className="bg-surface/30 p-2 rounded">
                    <span className="block text-[9px] font-mono text-fg-muted uppercase">Flag</span>
                    <TeamFlag name={selectedHome.name} fifaCode={selectedHome.fifa_code} size="md" className="mt-0.5" />
                  </div>
                  <div className="bg-surface/30 p-2 rounded">
                    <span className="block text-[9px] font-mono text-fg-muted uppercase">FIFA Rank</span>
                    <span className="block font-mono text-xs font-bold text-foreground mt-1">
                      #{selectedHome.fifa_ranking ?? "N/A"}
                    </span>
                  </div>
                  <div className="bg-surface/30 p-2 rounded">
                    <span className="block text-[9px] font-mono text-fg-muted uppercase">ELO Rating</span>
                    <span className="block font-mono text-xs font-bold text-cyan-400 mt-1">
                      {selectedHome.elo_rating ?? "N/A"}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Right Node: Away */}
            <div className="space-y-4 rounded-lg border border-border/40 bg-zinc-950/20 p-4">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono tracking-widest text-zinc-500 uppercase">NODE_02 // AWAY</span>
                {selectedAway && (
                  <span className="text-[10px] font-mono text-primary font-bold">
                    {selectedAway.confederation}
                  </span>
                )}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="away_team_combobox" className="text-xs font-mono tracking-wider text-zinc-400">Team Identifier</Label>
                <Combobox
                  id="away_team_combobox"
                  aria-label="Search for an away team"
                  value={awayTeamValue}
                  onValueChange={(v) => {
                    setValue("away_team", v, { shouldValidate: true });
                    const team = awayTeams.find((t) => t.name === v);
                    if (team) setSelectedAway(team);
                  }}
                  onSearchChange={setAwaySearch}
                  loading={awaySearching}
                  placeholder="Select away team…"
                  searchPlaceholder="Type team name…"
                  emptyMessage={awaySearch.length < 2 ? "Keep typing…" : "No matches found."}
                  options={awayTeams.map((t) => ({ value: t.name, label: t.name, description: t.country }))}
                />
                {errors.away_team && <p className="text-xs text-loss font-mono">{errors.away_team.message}</p>}
              </div>

              {/* Dynamic Preview */}
              {selectedAway && (
                <div className="pt-2 border-t border-border/20 grid grid-cols-3 gap-2 text-center">
                  <div className="bg-surface/30 p-2 rounded">
                    <span className="block text-[9px] font-mono text-fg-muted uppercase">Flag</span>
                    <TeamFlag name={selectedAway.name} fifaCode={selectedAway.fifa_code} size="md" className="mt-0.5" />
                  </div>
                  <div className="bg-surface/30 p-2 rounded">
                    <span className="block text-[9px] font-mono text-fg-muted uppercase">FIFA Rank</span>
                    <span className="block font-mono text-xs font-bold text-foreground mt-1">
                      #{selectedAway.fifa_ranking ?? "N/A"}
                    </span>
                  </div>
                  <div className="bg-surface/30 p-2 rounded">
                    <span className="block text-[9px] font-mono text-fg-muted uppercase">ELO Rating</span>
                    <span className="block font-mono text-xs font-bold text-cyan-400 mt-1">
                      {selectedAway.elo_rating ?? "N/A"}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Tournament Parameters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-mono tracking-wider text-zinc-400">Context Competition</Label>
              <Select value={tournamentValue ?? ""} onValueChange={(v) => setValue("tournament", v)}>
                <SelectTrigger className="border-border/40 font-mono text-xs h-10">
                  <SelectValue placeholder="Neutral Context (Optional)" />
                </SelectTrigger>
                <SelectContent>
                  {TOURNAMENTS.map((t) => (
                    <SelectItem key={t} value={t} className="font-mono text-xs">
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center justify-between rounded-lg border border-border/40 bg-zinc-950/20 px-4 h-10">
              <Label htmlFor="neutral_venue" className="cursor-pointer font-mono text-xs text-zinc-400">
                Neutral Pitch Venue
              </Label>
              <Switch
                id="neutral_venue"
                checked={neutralVenue}
                onCheckedChange={(checked) => setValue("neutral_venue", checked)}
              />
            </div>
          </div>

          {/* Submission and Control Actions */}
          <div className="flex gap-4 pt-4 border-t border-border/40">
            <Button type="submit" loading={loading} className="flex-1 bg-primary hover:bg-primary-hover text-slate-950 font-mono uppercase tracking-wider text-xs h-11 shadow-lg shadow-cyan-500/10 cursor-pointer">
              {!loading && <Brain className="h-4 w-4" />}
              {loading ? "Running Model Simulation..." : "Execute Simulation"}
              {!loading && <ArrowRight className="h-4 w-4" />}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="border-border text-foreground hover:bg-surface-2 h-11 px-4 cursor-pointer"
              onClick={() => {
                reset();
                setHomeSearch("");
                setAwaySearch("");
                setSelectedHome(null);
                setSelectedAway(null);
              }}
              aria-label="Reset simulation parameters"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
