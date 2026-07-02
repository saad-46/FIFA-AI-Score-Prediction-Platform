import type { Metadata } from "next";
import { BarChart3, TrendingUp, Target, Activity } from "lucide-react";
import { StatsCard } from "@/components/analytics/stats-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export const metadata: Metadata = { title: "Analytics" };

export default function AnalyticsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-emerald-400" />
          Analytics
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Historical match data and performance insights
        </p>
      </div>

      {/* Global stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Matches"
          value="44,341"
          icon={Activity}
          color="emerald"
          delay={0}
        />
        <StatsCard
          title="Avg Goals/Match"
          value="2.84"
          icon={Target}
          color="cyan"
          delay={0.05}
        />
        <StatsCard
          title="Home Win Rate"
          value="45.2%"
          icon={TrendingUp}
          color="purple"
          delay={0.1}
        />
        <StatsCard
          title="Draw Rate"
          value="22.1%"
          icon={BarChart3}
          color="amber"
          delay={0.15}
        />
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="goals">Goals</TabsTrigger>
          <TabsTrigger value="results">Results</TabsTrigger>
          <TabsTrigger value="model">Model</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Matches by Year</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-center h-48 text-slate-600">
                  Connect API to load chart data
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Result Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {[
                    { label: "Home Win", value: 45.2, color: "bg-emerald-500" },
                    { label: "Draw", value: 22.1, color: "bg-amber-500" },
                    { label: "Away Win", value: 32.7, color: "bg-red-500" },
                  ].map((item) => (
                    <div key={item.label} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span className="text-slate-300">{item.label}</span>
                        <span className="text-slate-400">{item.value}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-800">
                        <div
                          className={`h-full rounded-full ${item.color} transition-all duration-700`}
                          style={{ width: `${item.value}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="goals">
          <Card>
            <CardHeader>
              <CardTitle>Goal Distribution by Minute</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-center h-64 text-slate-600">
                Connect API to load goal distribution data
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="results">
          <Card>
            <CardHeader>
              <CardTitle>Most Common Scorelines</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-center h-64 text-slate-600">
                Connect API to load scoreline data
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="model">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { label: "Model Accuracy", value: "78.3%", desc: "Correct result predictions" },
              { label: "Mean Abs Error", value: "0.82", desc: "Average goal prediction error" },
              { label: "Training Samples", value: "35,472", desc: "Matches used for training" },
            ].map((m) => (
              <Card key={m.label}>
                <CardContent className="p-5 text-center">
                  <p className="text-3xl font-black text-emerald-400">{m.value}</p>
                  <p className="font-medium text-slate-200 mt-1">{m.label}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{m.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
