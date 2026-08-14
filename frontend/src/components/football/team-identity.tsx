import { cn } from "@/lib/utils";

interface TeamIdentityProps {
  name: string;
  fifaCode?: string;
  /** "avatar" = Circular/square monogram or flag (compact lists, tables).
   *  "chip"   = Flag badge + FIFA code pill (dense grids, group cards). */
  variant?: "avatar" | "chip";
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeClass = {
  sm: "h-6 w-6 text-xs",
  md: "h-8 w-8 text-base",
  lg: "h-10 w-10 text-xl",
};

const FLAG_MAP: Record<string, string> = {
  ARG: "🇦🇷", BRA: "🇧🇷", URU: "🇺🇾", COL: "🇨🇴", ECU: "🇪🇨", PAR: "🇵🇾", CHI: "🇨🇱", VEN: "🇻🇪", PER: "🇵🇪", BOL: "🇧🇴",
  FRA: "🇫🇷", GER: "🇩🇪", ENG: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", ESP: "🇪🇸", POR: "🇵🇹", ITA: "🇮🇹", NED: "🇳🇱", BEL: "🇧🇪", CRO: "🇭🇷", SUI: "🇨🇭",
  DEN: "🇩🇰", SWE: "🇸🇪", NOR: "🇳🇴", POL: "🇵🇱", UKR: "🇺🇦", AUT: "🇦🇹", SCO: "🏴󠁧󠁢󠁳󠁣󠁴󠁿", WAL: "🏴󠁧󠁢󠁷󠁬󠁳󠁿", TUR: "🇹🇷", CZE: "🇨🇿",
  HUN: "🇭🇺", SRB: "🇷🇸", SVN: "🇸🇮", SVK: "🇸🇰", ROU: "🇷🇴", GRE: "🇬🇷", IRL: "🇮🇪", NIR: "🏴󠁧󠁢󠁮󠁩󠁲󠁿", FIN: "🇫🇮", ISL: "🇮🇸",
  USA: "🇺🇸", MEX: "🇲🇽", CAN: "🇨🇦", CRC: "🇨🇷", PAN: "🇵🇦", JAM: "🇯🇲", HON: "🇭🇳", SLV: "🇸🇻", GUA: "🇬🇹", TTO: "🇹🇹",
  SEN: "🇸🇳", MAR: "🇲🇦", TUN: "🇹🇳", ALG: "🇩🇿", EGY: "🇪🇬", NGA: "🇳🇬", CMR: "🇨🇲", GHA: "🇬🇭", CIV: "🇨🇮", MLI: "🇲🇱",
  RSA: "🇿🇦", COD: "🇨🇩", ANG: "🇦🇴", JPN: "🇯🇵", KOR: "🇰🇷", AUS: "🇦🇺", IRN: "🇮🇷", KSA: "🇸🇦", QAT: "🇶🇦", UAE: "🇦🇪",
  IRQ: "🇮🇶", UZB: "🇺🇿", OMA: "🇴🇲", CHN: "🇨🇳", NZL: "🇳🇿",
  // Completes coverage of the 48 WC2026 qualifiers — these five had no entry,
  // so their cards fell back to the name heuristic and rendered no flag.
  BIH: "🇧🇦", CPV: "🇨🇻", CUW: "🇨🇼", HAI: "🇭🇹", JOR: "🇯🇴",
};

export function getCountryFlag(name: string, code?: string): string {
  const cleanCode = code?.trim().toUpperCase();
  if (cleanCode && FLAG_MAP[cleanCode]) {
    return FLAG_MAP[cleanCode];
  }
  
  const cleanName = name.trim().toLowerCase();
  if (cleanName.includes("argentina")) return "🇦🇷";
  if (cleanName.includes("brazil")) return "🇧🇷";
  if (cleanName.includes("france")) return "🇫🇷";
  if (cleanName.includes("germany")) return "🇩🇪";
  if (cleanName.includes("england")) return "🏴󠁧󠁢󠁥󠁮󠁧󠁿";
  if (cleanName.includes("spain")) return "🇪🇸";
  if (cleanName.includes("portugal")) return "🇵🇹";
  if (cleanName.includes("italy")) return "🇮🇹";
  if (cleanName.includes("netherlands") || cleanName === "holland") return "🇳🇱";
  if (cleanName.includes("belgium")) return "🇧🇪";
  if (cleanName.includes("croatia")) return "🇭🇷";
  if (cleanName.includes("switzerland")) return "🇨🇭";
  if (cleanName.includes("uruguay")) return "🇺🇾";
  if (cleanName.includes("colombia")) return "🇨🇴";
  if (cleanName.includes("ecuador")) return "🇪🇨";
  if (cleanName.includes("morocco")) return "🇲🇦";
  if (cleanName.includes("senegal")) return "🇸🇳";
  if (cleanName.includes("japan")) return "🇯🇵";
  if (cleanName.includes("korea")) return "🇰🇷";
  if (cleanName.includes("australia")) return "🇦🇺";
  if (cleanName.includes("united states") || cleanName === "usa" || cleanName.includes("us of a") || cleanName === "united states of america") return "🇺🇸";
  if (cleanName.includes("mexico")) return "🇲🇽";
  if (cleanName.includes("canada")) return "🇨🇦";
  if (cleanName.includes("costa rica")) return "🇨🇷";
  if (cleanName.includes("panama")) return "🇵🇦";
  if (cleanName.includes("saudi arabia")) return "🇸🇦";
  if (cleanName.includes("iran")) return "🇮🇷";
  if (cleanName.includes("ghana")) return "🇬🇭";
  if (cleanName.includes("cameroon")) return "🇨🇲";
  if (cleanName.includes("tunisia")) return "🇹🇳";
  if (cleanName.includes("egypt")) return "🇪🇬";
  if (cleanName.includes("algeria")) return "🇩🇿";
  if (cleanName.includes("denmark")) return "🇩🇰";
  if (cleanName.includes("poland")) return "🇵🇱";
  if (cleanName.includes("serbia")) return "🇷🇸";
  if (cleanName.includes("wales")) return "🏴󠁧󠁢󠁷󠁬󠁳󠁿";
  if (cleanName.includes("scotland")) return "🏴󠁧󠁢󠁳󠁣󠁴󠁿";
  if (cleanName.includes("turkey")) return "🇹🇷";
  if (cleanName.includes("peru")) return "🇵🇪";
  if (cleanName.includes("chile")) return "🇨🇱";
  if (cleanName.includes("ukraine")) return "🇺🇦";
  if (cleanName.includes("austria")) return "🇦🇹";
  if (cleanName.includes("ireland")) return "🇮🇪";
  if (cleanName.includes("new zealand")) return "🇳🇿";

  return "⚽";
}

export function TeamIdentity({ name, fifaCode, variant = "avatar", size = "md", className }: TeamIdentityProps) {
  const flag = getCountryFlag(name, fifaCode);
  const flagDisplay = (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded border border-border bg-surface-2/60 shadow-inner font-sans",
        sizeClass[size]
      )}
      aria-hidden="true"
    >
      <span className="leading-none select-none">{flag}</span>
    </div>
  );

  if (variant === "avatar") {
    return (
      <div className={cn("flex items-center gap-3", className)}>
        {flagDisplay}
        <span className="truncate text-sm font-medium text-foreground tracking-tight">{name}</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded border border-border bg-surface/50 py-1 pl-1.5 pr-2.5 shadow-sm backdrop-blur-sm",
        className
      )}
    >
      {flagDisplay}
      <span className="truncate text-xs font-mono font-bold uppercase tracking-wider text-foreground">
        {fifaCode ?? name.slice(0, 3).toUpperCase()}
      </span>
    </div>
  );
}
