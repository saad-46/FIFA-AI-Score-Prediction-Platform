import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TeamIdentity } from "@/components/football/team-identity";
import { cn } from "@/lib/utils";
import type { Fifa2026Team } from "@/types";

export interface GroupStanding extends Fifa2026Team {
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goalDifference: number;
  points: number;
}

interface GroupCardProps {
  groupLetter: string;
  teams: Fifa2026Team[];
  /** When provided, renders a full P/W/D/L/GD/Pts table instead of a plain list. */
  standings?: GroupStanding[];
  className?: string;
}

/** Covers both a plain 4-team group card and a full standings table — one
 * component with an optional prop, instead of two near-duplicate ones. */
export function GroupCard({ groupLetter, teams, standings, className }: GroupCardProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader className="border-b border-border pb-3">
        <CardTitle className="font-display text-xl font-semibold uppercase leading-none tracking-wide">Group {groupLetter}</CardTitle>
      </CardHeader>
      <CardContent>
        {standings && standings.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Team</TableHead>
                <TableHead className="text-center">P</TableHead>
                <TableHead className="text-center">W</TableHead>
                <TableHead className="text-center">D</TableHead>
                <TableHead className="text-center">L</TableHead>
                <TableHead className="text-center">GD</TableHead>
                <TableHead className="text-center">Pts</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {standings.map((s) => (
                <TableRow key={s.code}>
                  <TableCell>
                    <TeamIdentity name={s.name} fifaCode={s.code} size="sm" />
                  </TableCell>
                  <TableCell className="text-center font-mono">{s.played}</TableCell>
                  <TableCell className="text-center font-mono">{s.won}</TableCell>
                  <TableCell className="text-center font-mono">{s.drawn}</TableCell>
                  <TableCell className="text-center font-mono">{s.lost}</TableCell>
                  <TableCell className="text-center font-mono">
                    {s.goalDifference > 0 ? `+${s.goalDifference}` : s.goalDifference}
                  </TableCell>
                  <TableCell className="text-center font-mono font-semibold">{s.points}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <ul className="space-y-2.5 pt-4">
            {teams.map((t) => (
              <li key={t.code}>
                <TeamIdentity name={t.name} fifaCode={t.code} size="sm" />
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
