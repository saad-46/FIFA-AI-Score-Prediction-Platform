import type { Metadata } from "next";
import { Trophy } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Tournaments" };

const TOURNAMENTS = [
  { name: "FIFA World Cup", matches: 964, years: "1930–2022", color: "from-amber-600 to-yellow-600" },
  { name: "UEFA Euro", matches: 360, years: "1960–2024", color: "from-blue-600 to-cyan-600" },
  { name: "Copa America", matches: 847, years: "1916–2024", color: "from-emerald-600 to-teal-600" },
  { name: "Africa Cup of Nations", matches: 612, years: "1957–2024", color: "from-red-600 to-orange-600" },
  { name: "AFC Asian Cup", matches: 432, years: "1956–2023", color: "from-purple-600 to-violet-600" },
  { name: "CONCACAF Gold Cup", matches: 389, years: "1991–2023", color: "from-rose-600 to-pink-600" },
];

export default function TournamentsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Trophy className="h-6 w-6 text-emerald-400" />
          Tournaments
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Deep analytics for every major international tournament
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {TOURNAMENTS.map((tournament) => (
          <Card
            key={tournament.name}
            className="hover:border-slate-600 transition-all duration-200 cursor-pointer group overflow-hidden"
          >
            <div className={`h-1.5 bg-gradient-to-r ${tournament.color}`} />
            <CardContent className="p-5">
              <div className={`inline-flex rounded-lg bg-gradient-to-br ${tournament.color} p-2 mb-3`}>
                <Trophy className="h-4 w-4 text-white" />
              </div>
              <h3 className="font-semibold text-slate-200 group-hover:text-white transition-colors">
                {tournament.name}
              </h3>
              <div className="mt-2 flex items-center justify-between text-sm">
                <span className="text-slate-500">{tournament.years}</span>
                <span className="text-slate-400 font-medium">
                  {tournament.matches} matches
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tournament Comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center h-48 text-slate-600">
            Connect API to load tournament analytics
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
