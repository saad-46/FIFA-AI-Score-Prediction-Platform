"use client";

import { useMemo, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Trophy } from "lucide-react";
import { useBracket, useBracketIndex, useWc2026Teams, collectProgressionPath } from "@/hooks/use-wc2026";
import { getApiErrorMessage } from "@/lib/api/client";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { stageLabel, stageShortLabel } from "@/lib/wc2026";
import { BracketMatchCard } from "./bracket-match-card";
import { MatchDetailDialog } from "./match-detail-dialog";
import type { BracketNodeData, WcStage } from "@/types";

/** Knockout stages only — the group stage has its own standings view, and
 * folding 72 fixtures into the bracket would bury the progression. */
const KNOCKOUT_STAGES: WcStage[] = [
  "round_of_32",
  "round_of_16",
  "quarter_final",
  "semi_final",
  "final",
];

export function TournamentBracket() {
  const { data, error, isLoading, mutate } = useBracket();
  const { data: teamsData } = useWc2026Teams();
  const { byNumber, byStage } = useBracketIndex(data?.nodes);
  const reduceMotion = useReducedMotion();

  const [hovered, setHovered] = useState<number | null>(null);
  const [selected, setSelected] = useState<BracketNodeData | null>(null);
  const [mobileStage, setMobileStage] = useState<WcStage>("round_of_32");

  const highlightPath = useMemo(
    () => collectProgressionPath(hovered, byNumber),
    [hovered, byNumber]
  );

  if (isLoading) return <BracketSkeleton />;

  if (error) {
    return (
      <ErrorState
        title="Couldn't load the bracket"
        description={getApiErrorMessage(error)}
        onRetry={() => mutate()}
      />
    );
  }

  const thirdPlace = byStage.get("third_place")?.[0] ?? null;
  const final = byStage.get("final")?.[0] ?? null;
  const champion = final?.winner_team ?? null;

  const mobileMatches = byStage.get(mobileStage) ?? [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Trophy className="h-4 w-4 text-primary" aria-hidden="true" />
          <h2 className="font-mono text-xs uppercase tracking-wider text-foreground">
            Knockout Bracket
          </h2>
        </div>
        {champion && (
          <Badge variant="default" className="font-mono text-[10px] uppercase tracking-wider">
            Champion · {champion}
          </Badge>
        )}
      </div>

      {/* Desktop / laptop: real left-to-right progression. Scrolls horizontally
          inside its own container so the page body never scrolls sideways. */}
      <div className="hidden overflow-x-auto pb-2 lg:block">
        <div
          className="flex min-w-max items-stretch gap-5"
          onMouseLeave={() => setHovered(null)}
        >
          {KNOCKOUT_STAGES.map((stage, columnIndex) => {
            const matches = byStage.get(stage) ?? [];
            return (
              <section
                key={stage}
                className="flex w-44 shrink-0 flex-col"
                aria-label={stageLabel(stage)}
              >
                <h3 className="pb-2 text-center font-mono text-[10px] uppercase tracking-wider text-fg-muted">
                  {stageLabel(stage)}
                </h3>
                <div className="flex flex-1 flex-col justify-around gap-3">
                  {matches.map((node, rowIndex) => (
                    <motion.div
                      key={node.match_number}
                      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{
                        duration: 0.25,
                        ease: "easeOut",
                        delay: reduceMotion ? 0 : columnIndex * 0.05 + rowIndex * 0.015,
                      }}
                    >
                      <BracketMatchCard
                        node={node}
                        highlighted={highlightPath.has(node.match_number)}
                        dimmed={hovered !== null && !highlightPath.has(node.match_number)}
                        onHover={setHovered}
                        onSelect={setSelected}
                      />
                    </motion.div>
                  ))}
                </div>
              </section>
            );
          })}

          {/* The final's outcome, given its own column so the bracket resolves
              somewhere rather than just stopping. */}
          <section className="flex w-44 shrink-0 flex-col" aria-label="Result">
            <h3 className="pb-2 text-center font-mono text-[10px] uppercase tracking-wider text-fg-muted">
              Champion
            </h3>
            <div className="flex flex-1 flex-col justify-center gap-3">
              <ChampionCard champion={champion} reduceMotion={Boolean(reduceMotion)} />
              {thirdPlace && (
                <div className="space-y-1.5">
                  <p className="text-center font-mono text-[10px] uppercase tracking-wider text-fg-muted">
                    {stageLabel("third_place")}
                  </p>
                  <BracketMatchCard
                    node={thirdPlace}
                    highlighted={highlightPath.has(thirdPlace.match_number)}
                    dimmed={hovered !== null && !highlightPath.has(thirdPlace.match_number)}
                    onHover={setHovered}
                    onSelect={setSelected}
                  />
                </div>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* Tablet / mobile: stage-by-stage rather than a shrunken bracket, which
          would be unreadable at 390px. Hierarchy is kept via the stage tabs. */}
      <div className="lg:hidden">
        {/* Toggle buttons rather than role="tab": these swap the list below in
            place without the panel semantics a real tablist promises, and the
            page already has a genuine Radix tablist above that this would
            otherwise be confused with by assistive tech. */}
        <div
          className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-2"
          role="group"
          aria-label="Bracket stage"
        >
          {[...KNOCKOUT_STAGES, "third_place" as WcStage].map((stage) => (
            <button
              key={stage}
              type="button"
              aria-pressed={mobileStage === stage}
              onClick={() => setMobileStage(stage)}
              className={cn(
                "shrink-0 rounded-full border px-3 py-1.5 font-mono text-[11px] uppercase tracking-wider transition-colors",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                mobileStage === stage
                  ? "border-primary/50 bg-primary/15 text-primary"
                  : "border-border bg-surface text-fg-muted hover:text-foreground"
              )}
            >
              {stageShortLabel(stage)}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-2.5 pt-2 sm:grid-cols-2">
          {mobileMatches.map((node, index) => (
            <motion.div
              key={node.match_number}
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, ease: "easeOut", delay: reduceMotion ? 0 : index * 0.02 }}
            >
              <BracketMatchCard node={node} onSelect={setSelected} />
            </motion.div>
          ))}
        </div>

        {mobileStage === "final" && champion && (
          <div className="pt-3">
            <ChampionCard champion={champion} reduceMotion={Boolean(reduceMotion)} />
          </div>
        )}
      </div>

      <MatchDetailDialog
        node={selected}
        teams={teamsData?.teams}
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
      />
    </div>
  );
}

function ChampionCard({ champion, reduceMotion }: { champion: string | null; reduceMotion: boolean }) {
  if (!champion) return null;
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut", delay: reduceMotion ? 0 : 0.25 }}
      className="rounded-lg border border-primary/40 bg-primary/10 px-3 py-4 text-center"
    >
      <Trophy className="mx-auto h-5 w-5 text-primary" aria-hidden="true" />
      <p className="pt-1.5 font-mono text-[10px] uppercase tracking-wider text-fg-muted">
        World Champion
      </p>
      <p className="pt-0.5 text-sm font-bold text-foreground">{champion}</p>
    </motion.div>
  );
}

function BracketSkeleton() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-5 w-40" />
      <div className="flex gap-5 overflow-hidden">
        {[16, 8, 4, 2, 1].map((count, columnIndex) => (
          <div key={columnIndex} className="flex w-44 shrink-0 flex-col gap-3">
            <Skeleton className="mx-auto h-3 w-20" />
            {Array.from({ length: Math.min(count, 6) }).map((_, index) => (
              <Skeleton key={index} className="h-16 w-full rounded-lg" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
