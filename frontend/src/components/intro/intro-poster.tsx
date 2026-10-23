/**
 * The still that stands in for the 3D intro: while it loads, when motion is
 * reduced, and when WebGL is unavailable or fails. Pure CSS, so there is
 * always something on screen and always a way into the site.
 */
export function IntroPoster({ loading = false }: { loading?: boolean }) {
  return (
    <div className="relative flex h-full w-full flex-col items-center justify-center overflow-hidden bg-[#04060b] px-6 text-center">
      {/* One floodlight cone over a strip of pitch. */}
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(60% 55% at 50% 0%, rgba(150,190,255,0.20), transparent 70%), linear-gradient(to top, #0b2a14 0%, #071a0e 14%, transparent 34%)",
        }}
      />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-[14%] h-px bg-white/25" />
      <div className="relative">
        <p className="font-display text-6xl font-bold uppercase leading-none tracking-wider text-foreground sm:text-8xl">
          FIFA <span className="text-primary">AI</span>
        </p>
        <p className="mx-auto mt-4 max-w-md text-sm leading-relaxed text-fg-muted sm:text-base">
          {loading ? "Loading the 3D intro…" : "The 2026 World Cup, played and measured."}
        </p>
        <a
          href="#main"
          className="mt-7 inline-flex h-11 items-center justify-center rounded-lg bg-primary px-8 text-base font-semibold text-primary-ink transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-[#04060b]"
        >
          Enter the site
        </a>
      </div>
    </div>
  );
}
