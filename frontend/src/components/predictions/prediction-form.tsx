"use client";

import React, { useId, useMemo, useState } from "react";
import { ArrowLeftRight, RotateCcw } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { predictionsApi } from "@/lib/api/predictions";
import { teamsApi } from "@/lib/api/teams";
import { getApiErrorMessage } from "@/lib/api/client";
import { toast } from "@/hooks/use-toast";
import { TeamFlag } from "@/components/football/team-flag";
import { cn } from "@/lib/utils";
import type { PredictionResult, Team } from "@/types";

const schema = z.object({
  home_team: z.string().min(1, "Choose the first team"),
  away_team: z.string().min(1, "Choose the second team"),
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

/** Sentinel for "no competition chosen": Radix Select items cannot have an empty value. */
const ANY_COMPETITION = "__any__";

interface PredictionFormProps {
  onResult: (result: PredictionResult) => void;
  onStartPredict: () => void;
  onPredictError: () => void;
}

/** Builds a Combobox option for a WC2026 team: flag, name, code + group, and
 * rank/Elo on the right. Defined once so the two selectors cannot drift apart. */
function teamOption(t: Team): ComboboxOption {
  const meta = [t.fifa_code, t.wc2026_group ? `Group ${t.wc2026_group}` : null].filter(Boolean).join(" · ");
  return {
    value: t.name,
    label: t.name,
    description: meta || t.country,
    leading: <TeamFlag name={t.name} fifaCode={t.fifa_code} size="sm" />,
    trailing: (
      <span className="tabular text-[11px] text-fg-muted">
        {t.fifa_ranking != null ? `#${t.fifa_ranking}` : "—"}
        {t.elo_rating != null ? ` · ${t.elo_rating}` : ""}
      </span>
    ),
  };
}

/**
 * The fixture builder.
 *
 * Laid out as a fixture — one side, "v", the other side — because that is what
 * the user is describing. The previous form boxed each side as "NODE_01 // HOME"
 * and "NODE_02 // AWAY" under a "Simulation Parameters" heading: a football
 * match dressed as a server rack.
 *
 * Venue is a two-option choice rather than a "neutral" toggle. The toggle hid
 * the consequence of its off state: the first team silently received home
 * advantage. Naming both options makes the default visible.
 */
export function PredictionForm({ onResult, onStartPredict, onPredictError }: PredictionFormProps) {
  const [loading, setLoading] = useState(false);
  const [homeSearch, setHomeSearch] = useState("");
  const [awaySearch, setAwaySearch] = useState("");
  const uid = useId();

  // The 48 WC2026 qualifiers, not /teams/search. That endpoint queries all 335
  // rows in the teams table, which still contains non-national entities from
  // the legacy seed ("Central Spain", "Asturias", "Ticino") — they must never
  // be selectable as a 2026 fixture. Filtering happens client-side over a
  // fixed 48-item list, so there is no per-keystroke request either.
  const {
    data: rosterData,
    isLoading: rosterLoading,
    error: rosterError,
    mutate: retryRoster,
  } = useSWR("wc2026-team-directory", teamsApi.getWc2026Teams, { revalidateOnFocus: false });
  const roster = useMemo(() => rosterData ?? [], [rosterData]);

  const filterRoster = (query: string, exclude?: string) => {
    const q = query.trim().toLowerCase();
    return roster.filter((t) => {
      if (exclude && t.name === exclude) return false;
      if (!q) return true;
      return t.name.toLowerCase().includes(q) || (t.fifa_code ?? "").toLowerCase().includes(q);
    });
  };

  const {
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { home_team: "", away_team: "", neutral_venue: true },
  });

  const homeTeamValue = watch("home_team");
  const awayTeamValue = watch("away_team");
  const neutralVenue = watch("neutral_venue");
  const tournamentValue = watch("tournament");

  const selectedHome = roster.find((t) => t.name === homeTeamValue) ?? null;
  const selectedAway = roster.find((t) => t.name === awayTeamValue) ?? null;

  // Each side's list excludes the other side's pick, so a team cannot be
  // selected against itself.
  const homeTeams = filterRoster(homeSearch, awayTeamValue);
  const awayTeams = filterRoster(awaySearch, homeTeamValue);

  const onSubmit = async (values: FormValues) => {
    // `loading` also disables the button, but a second Enter keypress can land
    // before React re-renders; this guard is what actually prevents a duplicate.
    if (loading) return;
    if (values.home_team === values.away_team) {
      toast({ title: "Pick two different teams", description: "A team cannot play itself.", variant: "destructive" });
      return;
    }
    setLoading(true);
    onStartPredict();
    try {
      const result = await predictionsApi.predict({
        ...values,
        tournament: values.tournament && values.tournament !== ANY_COMPETITION ? values.tournament : undefined,
      });
      onResult(result);
    } catch (err: unknown) {
      toast({ title: "Prediction unavailable", description: getApiErrorMessage(err), variant: "destructive" });
      onPredictError();
    } finally {
      setLoading(false);
    }
  };

  const swap = () => {
    setValue("home_team", awayTeamValue, { shouldValidate: Boolean(awayTeamValue) });
    setValue("away_team", homeTeamValue, { shouldValidate: Boolean(homeTeamValue) });
  };

  const homeError = `${uid}-home-error`;
  const awayError = `${uid}-away-error`;
  const venueName = `${uid}-venue`;

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      noValidate
      aria-label="Match to predict"
      className="@container rounded-lg border border-border bg-surface"
    >
      {rosterError && (
        <p role="alert" className="border-b border-border px-5 py-3 text-sm text-fg-muted">
          The team list could not be loaded: {getApiErrorMessage(rosterError)}{" "}
          <button type="button" onClick={() => retryRoster()} className="font-semibold text-primary hover:underline">
            Retry
          </button>
        </p>
      )}

      {/* ── The fixture ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 items-start gap-4 p-5 @2xl:grid-cols-[1fr_auto_1fr] @2xl:gap-6">
        <TeamSlot
          side="first"
          label={neutralVenue ? "Team A" : "Home team"}
          inputId={`${uid}-home`}
          errorId={homeError}
          error={errors.home_team?.message}
          team={selectedHome}
          value={homeTeamValue}
          options={homeTeams.map(teamOption)}
          loading={rosterLoading}
          onSearchChange={setHomeSearch}
          onValueChange={(v) => setValue("home_team", v, { shouldValidate: true })}
        />

        <div className="flex items-center justify-center gap-3 @2xl:mt-7 @2xl:flex-col @2xl:gap-2">
          <span className="font-display text-2xl font-semibold uppercase text-fg-subtle" aria-hidden="true">
            v
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={swap}
            disabled={!homeTeamValue && !awayTeamValue}
            aria-label="Swap the two teams"
            title="Swap the two teams"
          >
            <ArrowLeftRight aria-hidden="true" />
          </Button>
        </div>

        <TeamSlot
          side="second"
          label={neutralVenue ? "Team B" : "Away team"}
          inputId={`${uid}-away`}
          errorId={awayError}
          error={errors.away_team?.message}
          team={selectedAway}
          value={awayTeamValue}
          options={awayTeams.map(teamOption)}
          loading={rosterLoading}
          onSearchChange={setAwaySearch}
          onValueChange={(v) => setValue("away_team", v, { shouldValidate: true })}
        />
      </div>

      {/* ── Context ──────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-5 border-t border-border p-5 @2xl:grid-cols-2">
        <fieldset>
          <legend className="eyebrow mb-2">Venue</legend>
          <div className="grid grid-cols-2 gap-2">
            <VenueOption
              name={venueName}
              checked={neutralVenue}
              onChange={() => setValue("neutral_venue", true)}
              title="Neutral ground"
              description="No home advantage. The order of the teams does not matter."
            />
            <VenueOption
              name={venueName}
              checked={!neutralVenue}
              onChange={() => setValue("neutral_venue", false)}
              title={selectedHome ? `${selectedHome.name} at home` : "First team at home"}
              description="The first team gets home advantage."
            />
          </div>
        </fieldset>

        <div>
          <Label htmlFor={`${uid}-competition`} className="eyebrow mb-2 block">
            Competition <span className="font-normal normal-case tracking-normal">(optional)</span>
          </Label>
          <Select
            value={tournamentValue ?? ANY_COMPETITION}
            onValueChange={(v) => setValue("tournament", v === ANY_COMPETITION ? undefined : v)}
          >
            <SelectTrigger id={`${uid}-competition`} className="h-11">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY_COMPETITION}>Not specified</SelectItem>
              {TOURNAMENTS.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="mt-1.5 text-xs text-fg-subtle">The level of competition the match is played in.</p>
        </div>
      </div>

      {/* ── Actions ──────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4">
        <p className="text-xs text-fg-subtle">Teams are the 48 World Cup 2026 qualifiers.</p>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              reset({ home_team: "", away_team: "", tournament: undefined, neutral_venue: true });
              setHomeSearch("");
              setAwaySearch("");
            }}
          >
            <RotateCcw aria-hidden="true" />
            Reset
          </Button>
          <Button type="submit" size="lg" loading={loading} className="min-w-40">
            {loading ? "Predicting…" : "Predict match"}
          </Button>
        </div>
      </div>
    </form>
  );
}

interface TeamSlotProps {
  side: "first" | "second";
  label: string;
  inputId: string;
  errorId: string;
  error?: string;
  team: Team | null;
  value: string;
  options: ComboboxOption[];
  loading: boolean;
  onSearchChange: (q: string) => void;
  onValueChange: (v: string) => void;
}

function TeamSlot({
  side,
  label,
  inputId,
  errorId,
  error,
  team,
  value,
  options,
  loading,
  onSearchChange,
  onValueChange,
}: TeamSlotProps) {
  return (
    <div className="min-w-0 space-y-3">
      <div className="space-y-1.5">
        {/* The visible label names the control: <button> is labelable, so this
            <label> wins the accessible-name computation over the Combobox's
            aria-label (which only reaches the popover's search input). */}
        <Label htmlFor={inputId} className="eyebrow block">
          {label}
        </Label>
        <Combobox
          id={inputId}
          aria-label={`Search for the ${side} team`}
          aria-invalid={Boolean(error) || undefined}
          aria-describedby={error ? errorId : undefined}
          value={value}
          onValueChange={onValueChange}
          onSearchChange={onSearchChange}
          loading={loading}
          placeholder="Choose a team…"
          searchPlaceholder="Type a team name or code…"
          emptyMessage="No 2026 team matches that."
          options={options}
        />
        {error && (
          <p id={errorId} role="alert" className="text-xs font-medium text-loss">
            {error}
          </p>
        )}
      </div>

      {/* The chosen team's identity. The frame keeps its height when empty so
          picking a team does not push the rest of the form down. */}
      <div
        className={cn(
          "flex min-h-[4.5rem] items-center gap-3 rounded-md border px-3 py-2.5",
          team ? "border-border bg-surface-2" : "border-dashed border-border"
        )}
      >
        {team ? (
          <>
            <TeamFlag name={team.name} fifaCode={team.fifa_code} size="lg" />
            <div className="min-w-0 flex-1">
              <p className="truncate font-display text-2xl font-semibold uppercase leading-none tracking-wide text-foreground">
                {team.name}
              </p>
              <p className="mt-1 truncate text-xs text-fg-muted">
                {[team.confederation, team.wc2026_group ? `Group ${team.wc2026_group}` : null].filter(Boolean).join(" · ")}
              </p>
            </div>
            <dl className="flex shrink-0 gap-4 text-right">
              <div>
                <dt className="eyebrow">Rank</dt>
                <dd className="tabular text-sm font-semibold text-foreground">
                  {team.fifa_ranking != null ? `#${team.fifa_ranking}` : "—"}
                </dd>
              </div>
              <div>
                <dt className="eyebrow">Elo</dt>
                <dd className="tabular text-sm font-semibold text-foreground">{team.elo_rating ?? "—"}</dd>
              </div>
            </dl>
          </>
        ) : (
          <p className="text-sm text-fg-subtle">No team chosen yet</p>
        )}
      </div>
    </div>
  );
}

function VenueOption({
  name,
  checked,
  onChange,
  title,
  description,
}: {
  name: string;
  checked: boolean;
  onChange: () => void;
  title: string;
  description: string;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer gap-2.5 rounded-md border p-3 transition-colors",
        "has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-ring",
        checked ? "border-primary bg-primary/5" : "border-border hover:border-border-strong"
      )}
    >
      <input
        type="radio"
        name={name}
        checked={checked}
        onChange={onChange}
        className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--primary)] focus:outline-none"
      />
      <span className="min-w-0">
        <span className="block text-sm font-semibold leading-tight text-foreground">{title}</span>
        <span className="mt-0.5 block text-xs leading-snug text-fg-muted">{description}</span>
      </span>
    </label>
  );
}
