"use client";

import React, { useState } from "react";
import { Brain, ArrowRight, RefreshCw } from "lucide-react";
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
import type { PredictionResult } from "@/types";
import { toast } from "@/hooks/use-toast";
import { useTeamSearch } from "@/hooks/use-team-search";

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
  const { results: homeTeams, loading: homeSearching } = useTeamSearch(homeSearch);
  const { results: awayTeams, loading: awaySearching } = useTeamSearch(awaySearch);

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
      toast({ title: "Error", description: getApiErrorMessage(err), variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card glow>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-primary" aria-hidden="true" />
          AI Match Prediction
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="home_team_combobox">Home Team</Label>
              <Combobox
                id="home_team_combobox"
                aria-label="Search for a home team"
                value={homeTeamValue}
                onValueChange={(v) => setValue("home_team", v, { shouldValidate: true })}
                onSearchChange={setHomeSearch}
                loading={homeSearching}
                placeholder="Search team…"
                searchPlaceholder="Type at least 2 characters…"
                emptyMessage={homeSearch.length < 2 ? "Keep typing…" : "No teams found."}
                options={homeTeams.map((t) => ({ value: t.name, label: t.name, description: t.country }))}
              />
              {errors.home_team && <p className="text-xs text-loss">{errors.home_team.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="away_team_combobox">Away Team</Label>
              <Combobox
                id="away_team_combobox"
                aria-label="Search for an away team"
                value={awayTeamValue}
                onValueChange={(v) => setValue("away_team", v, { shouldValidate: true })}
                onSearchChange={setAwaySearch}
                loading={awaySearching}
                placeholder="Search team…"
                searchPlaceholder="Type at least 2 characters…"
                emptyMessage={awaySearch.length < 2 ? "Keep typing…" : "No teams found."}
                options={awayTeams.map((t) => ({ value: t.name, label: t.name, description: t.country }))}
              />
              {errors.away_team && <p className="text-xs text-loss">{errors.away_team.message}</p>}
            </div>
          </div>

          <div className="space-y-2">
            <Label>Tournament (optional)</Label>
            <Select value={tournamentValue ?? ""} onValueChange={(v) => setValue("tournament", v)}>
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

          <div className="flex items-center gap-3">
            <Switch
              id="neutral_venue"
              checked={neutralVenue}
              onCheckedChange={(checked) => setValue("neutral_venue", checked)}
            />
            <Label htmlFor="neutral_venue" className="cursor-pointer">
              Neutral venue
            </Label>
          </div>

          <div className="flex gap-3">
            <Button type="submit" loading={loading} className="flex-1" variant="gradient" size="lg">
              {!loading && <Brain className="h-4 w-4" />}
              {loading ? "Predicting..." : "Predict Match"}
              {!loading && <ArrowRight className="h-4 w-4" />}
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
