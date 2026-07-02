import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Shield, TrendingUp, Target, Activity } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatsCard } from "@/components/analytics/stats-card";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export const metadata: Metadata = { title: "Team Details" };

interface TeamPageProps {
  params: Promise<{ id: string }>;
}

export default async function TeamPage({ params }: TeamPageProps) {
  const { id } = await params;

  // In production: fetch team data from API
  // const team = await teamsApi.getById(id);
  // if (!team) notFound();

  return (
    <div className="space-y-8">
      {/* Team header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-slate-800 text-2xl font-black text-slate-300">
          T
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-white">Team Details</h1>
          <p className="text-slate-400 text-sm">ID: {id}</p>
        </div>
        <Button variant="gradient" asChild>
          <Link href={`/predict?home=${id}`}>
            Predict with this team
          </Link>
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard title="Win Rate" value="—" icon={TrendingUp} color="emerald" />
        <StatsCard title="Goals Scored" value="—" icon={Target} color="cyan" />
        <StatsCard title="Clean Sheets" value="—" icon={Shield} color="purple" />
        <StatsCard title="Matches" value="—" icon={Activity} color="amber" />
      </div>

      <Tabs defaultValue="stats">
        <TabsList>
          <TabsTrigger value="stats">Statistics</TabsTrigger>
          <TabsTrigger value="matches">Match History</TabsTrigger>
          <TabsTrigger value="trend">Performance Trend</TabsTrigger>
        </TabsList>
        <TabsContent value="stats">
          <Card>
            <CardContent className="flex items-center justify-center h-48 text-slate-600">
              Connect API to load team statistics
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="matches">
          <Card>
            <CardContent className="flex items-center justify-center h-48 text-slate-600">
              Connect API to load match history
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="trend">
          <Card>
            <CardContent className="flex items-center justify-center h-48 text-slate-600">
              Connect API to load performance trend
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
