import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // Refresh session — do not remove this
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // No route is gated at the edge any more: the product is browsable without an
  // account, so a visitor must never be bounced to /auth/login just for opening
  // a page. /dashboard is fully public (its endpoint returns global stats and
  // simply omits the per-user block for anonymous callers), while /saved and
  // /profile render their own guest states instead of redirecting.
  //
  // This does not weaken security, which lives in two places that still apply:
  //   * the API — /predictions/{save,saved,accuracy} require get_current_user
  //     and answer 401 without a token;
  //   * Postgres RLS — profiles and saved_predictions are owner-scoped
  //     (auth.uid() = id / user_id), so anonymous reads return nothing rather
  //     than another user's rows.
  //
  // The mechanism is kept rather than deleted: a future genuinely
  // account-only route can be added to this list, and the getUser() call above
  // must stay regardless — it refreshes the session cookie on every request.
  const protectedRoutes: string[] = [];
  const isProtected = protectedRoutes.some((route) =>
    request.nextUrl.pathname.startsWith(route)
  );

  if (isProtected && !user) {
    const url = request.nextUrl.clone();
    url.pathname = "/auth/login";
    url.searchParams.set("redirectTo", request.nextUrl.pathname);
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}
