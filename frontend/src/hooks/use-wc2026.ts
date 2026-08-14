"use client";

import useSWR from "swr";
import { useMemo } from "react";
import { wc2026Api } from "@/lib/api/wc2026";
import type { BracketNodeData, WcStage } from "@/types";

/**
 * Data hooks for the WC2026 tournament experience.
 *
 * These four endpoints are static for the lifetime of a deploy (the tournament
 * is complete and the prediction ledger is frozen), so revalidation is turned
 * off entirely — refetching on every window focus would be pure waste.
 */
const STATIC_SWR_CONFIG = {
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  revalidateIfStale: false,
} as const;

export function useBracket() {
  return useSWR("wc2026-bracket", wc2026Api.getBracket, STATIC_SWR_CONFIG);
}

export function useStandings() {
  return useSWR("wc2026-standings", wc2026Api.getStandings, STATIC_SWR_CONFIG);
}

export function useWc2026Teams() {
  return useSWR("wc2026-teams", wc2026Api.getTeams, STATIC_SWR_CONFIG);
}

export function useBacktest() {
  return useSWR("wc2026-backtest", wc2026Api.getBacktest, STATIC_SWR_CONFIG);
}

/**
 * Groups bracket nodes by stage and indexes them by match number.
 *
 * Both shapes are needed together and on every render of the bracket: the
 * per-stage lists build the columns, and the index resolves `home_source`
 * /`feeds_winner_to` pointers into real matches for the connectors and the
 * hover path. Deriving them once here keeps that work out of the render path.
 */
export function useBracketIndex(nodes: BracketNodeData[] | undefined) {
  return useMemo(() => {
    const byNumber = new Map<number, BracketNodeData>();
    const byStage = new Map<WcStage, BracketNodeData[]>();

    for (const node of nodes ?? []) {
      byNumber.set(node.match_number, node);
      const bucket = byStage.get(node.stage);
      if (bucket) bucket.push(node);
      else byStage.set(node.stage, [node]);
    }

    for (const bucket of byStage.values()) {
      bucket.sort((a, b) => a.match_number - b.match_number);
    }

    return { byNumber, byStage };
  }, [nodes]);
}

/**
 * Walks the progression graph from a match to collect the path it belongs to —
 * every feeder match that could have produced its participants, plus every
 * downstream match its winner feeds into.
 *
 * Used for the bracket's hover highlight. Walks `home_source`/`away_source`
 * backwards and `feeds_winner_to` forwards, so the highlighted path always
 * reflects the real tournament graph rather than a positional guess.
 */
export function collectProgressionPath(
  matchNumber: number | null,
  byNumber: Map<number, BracketNodeData>
): Set<number> {
  const path = new Set<number>();
  if (matchNumber === null) return path;

  const walkBack = (number: number) => {
    if (path.has(number)) return;
    path.add(number);
    const node = byNumber.get(number);
    if (!node) return;
    for (const source of [node.home_source, node.away_source]) {
      if (source?.match_number != null) walkBack(source.match_number);
    }
  };

  const walkForward = (number: number) => {
    const node = byNumber.get(number);
    if (!node?.feeds_winner_to) return;
    if (path.has(node.feeds_winner_to)) return;
    path.add(node.feeds_winner_to);
    walkForward(node.feeds_winner_to);
  };

  walkBack(matchNumber);
  walkForward(matchNumber);
  return path;
}
