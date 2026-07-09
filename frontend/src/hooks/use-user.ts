"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import type { User as SupabaseUser } from "@supabase/supabase-js";

/**
 * Client-side auth state, kept in sync with the Supabase session (including
 * sign-in/sign-out events). Use this in Client Components that need to know
 * whether the current visitor is authenticated — Server Components should
 * call supabase.auth.getUser() directly instead (see (app)/layout.tsx).
 */
export function useUser() {
  const [user, setUser] = useState<SupabaseUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = createClient();

    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  return { user, isAuthenticated: !!user, loading };
}
