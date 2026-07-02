"use client";

import React, { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Brain, Loader2, ArrowRight, RefreshCw } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { predictionsApi } from "@/lib/api/predictions";
import { teamsApi } from "@/lib/api/teams";
import type { PredictionResult, Team } from "@/types";
import { toast } from "@/hooks/use-toast";
import { useDebounce } from "@/hooks/use-debounce";

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
}

export function PredictionForm({ onResult }: PredictionFormProps) {
  const [loading, setLoading] = useState(false);
  const [homeSearch, setHomeSearch] = useState("");
  const [awaySearch, setAwaySearch] = useState("");
  const [homeTeams, setHomeTeams] = useState<Team[]>([]);
  const [awayTeams, setAwayTeams] = useState<Team[]>([]);
  const [homeSearching, setHomeSearching] = useState(false);
  const [awaySearching, setAwaySearching] = useState(false);

  const {
    register,
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

  const debouncedHomeSearch = useDebounce(homeSearch, 300);
  const debouncedAwaySearch = useDebounce(awaySearch, 300);

  React.useEffect(() => {
    if (!debouncedHomeSearch || debouncedHomeSearch.length < 2) {
      setHomeTeams([]);
      return;
    }
    setHomeSearching(true);
    teamsApi
      .search(debouncedHomeSearch)
      .then(setHomeTeams)
      .catch(() => setHomeTeams([]))
      .finally(() => setHomeSearching(false));
  }, [debouncedHomeSearch]);

  React.useEffect(() => {
    if (!debouncedAwaySearch || debouncedAwaySearch.length < 2) {
      setAwayTeams([]);
      return;
    }
    setAwaySearching(true);
    teamsApi
      .search(debouncedAwaySearch)
      .then(setAwayTeams)
      .catch(() => setAwayTeams([]))
      .finally(() => setAwaySearching(false));
  }, [debouncedAwaySearch]);

  const onSubmit = async (values: FormValues) => {
    if (values.home_team === values.away_team) {
      toast({
        title: "Invalid selection",
        description: "Home and away teams must be different.",
        variant: "destructive",
      });
      return;
    }
    setLoading(true);
    try {
      const result = await predictionsApi.predict(values);
      onResult(result);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Prediction failed. Try again.";
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card glow>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-emerald-400" />
          AI Match Prediction
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Home Team */}
            <div className="space-y-2">
              <Label htmlFor="home_team">Home Team</Label>
              <div className="relative">
                <Input
                  id="home_team_search"
                  placeholder="Search team..."
                  value={homeSearch}
                  onChange={(e) => setHomeSearch(e.target.value)}
                  autoComplete="off"
                />
                {homeSearching && (
                  <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-slate-400" />
                )}
                {homeTeams.length > 0 && (
                  <div className="absolute z-10 mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 shadow-xl max-h-48 overflow-y-auto">
                    {homeTeams.map((team) => (
                      <button
                        key={team.id}
                        type="button"
                        className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 transition-colors"
                        onClick={() => {
                          setValue("home_team", team.name);
                          setHomeSearch(team.name);
                          setHomeTeams([]);
                        }}
                      >
                        <span className="font-medium">{team.name}</span>
                        <span className="text-slate-500 text-xs ml-auto">
                          {team.country}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {homeTeamValue && (
                <p className="text-xs text-emerald-400">✓ {homeTeamValue}</p>
              )}
              {errors.home_team && (
                <p className="text-xs text-red-400">{errors.home_team.message}</p>
              )}
              <input type="hidden" {...register("home_team")} />
            </div>

            {/* Away Team */}
            <div className="space-y-2">
              <Label htmlFor="away_team">Away Team</Label>
              <div className="relative">
                <Input
                  id="away_team_search"
                  placeholder="Search team..."
                  value={awaySearch}
                  onChange={(e) => setAwaySearch(e.target.value)}
                  autoComplete="off"
                />
                {awaySearching && (
                  <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-slate-400" />
                )}
                {awayTeams.length > 0 && (
                  <div className="absolute z-10 mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 shadow-xl max-h-48 overflow-y-auto">
                    {awayTeams.map((team) => (
                      <button
                        key={team.id}
                        type="button"
                        className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-800 transition-colors"
                        onClick={() => {
                          setValue("away_team", team.name);
                          setAwaySearch(team.name);
                          setAwayTeams([]);
                        }}
                      >
                        <span className="font-medium">{team.name}</span>
                        <span className="text-slate-500 text-xs ml-auto">
                          {team.country}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {awayTeamValue && (
                <p className="text-xs text-emerald-400">✓ {awayTeamValue}</p>
              )}
              {errors.away_team && (
                <p className="text-xs text-red-400">{errors.away_team.message}</p>
              )}
              <input type="hidden" {...register("away_team")} />
            </div>
          </div>

          {/* Tournament */}
          <div className="space-y-2">
            <Label>Tournament (optional)</Label>
            <Select onValueChange={(v) => setValue("tournament", v)}>
              <SelectTrigger>
                <SelectValue placeholder="Select tournament..." />
              </SelectTrigger>
              <SelectContent>
                {TOURNAMENTS.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Neutral venue */}
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="neutral_venue"
              {...register("neutral_venue")}
              className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
            />
            <Label htmlFor="neutral_venue" className="cursor-pointer">
              Neutral venue
            </Label>
          </div>

          <div className="flex gap-3">
            <Button
              type="submit"
              disabled={loading}
              className="flex-1"
              variant="gradient"
              size="lg"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Predicting...
                </>
              ) : (
                <>
                  <Brain className="h-4 w-4" />
                  Predict Match
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={() => {
                reset();
                setHomeSearch("");
                setAwaySearch("");
              }}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
