"use client";

import useSWR from "swr";
import { teamsApi } from "@/lib/api/teams";
import { useDebounce } from "@/hooks/use-debounce";

/** Debounced team search backed by SWR — request de-duplication and
 * race-safety (a stale response can never overwrite a newer query's result)
 * come from SWR's own key-scoped caching, no manual effect needed. */
export function useTeamSearch(query: string, delay = 300) {
  const debounced = useDebounce(query, delay);
  const shouldFetch = debounced.length >= 2;

  const { data, isLoading } = useSWR(
    shouldFetch ? ["team-search", debounced] : null,
    ([, q]: [string, string]) => teamsApi.search(q)
  );

  return { results: data ?? [], loading: shouldFetch && isLoading };
}
