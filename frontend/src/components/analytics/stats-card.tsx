"use client";

import React from "react";
import { motion } from "framer-motion";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: { value: number; label: string };
  color?: "emerald" | "cyan" | "amber" | "red" | "purple";
  delay?: number;
}

const colorMap = {
  emerald: {
    icon: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20",
    trend: "text-emerald-400",
  },
  cyan: {
    icon: "text-cyan-400",
    bg: "bg-cyan-500/10",
    border: "border-cyan-500/20",
    trend: "text-cyan-400",
  },
  amber: {
    icon: "text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/20",
    trend: "text-amber-400",
  },
  red: {
    icon: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/20",
    trend: "text-red-400",
  },
  purple: {
    icon: "text-purple-400",
    bg: "bg-purple-500/10",
    border: "border-purple-500/20",
    trend: "text-purple-400",
  },
};

export function StatsCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color = "emerald",
  delay = 0,
}: StatsCardProps) {
  const colors = colorMap[color];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
    >
      <Card className={cn("border", colors.border)}>
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <p className="text-sm text-slate-400">{title}</p>
              <p className="mt-1 text-2xl font-bold text-slate-100">{value}</p>
              {subtitle && (
                <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
              )}
              {trend && (
                <p className={cn("mt-1 text-xs font-medium", colors.trend)}>
                  {trend.value > 0 ? "↑" : "↓"} {Math.abs(trend.value)}%{" "}
                  {trend.label}
                </p>
              )}
            </div>
            <div className={cn("rounded-lg p-2.5", colors.bg)}>
              <Icon className={cn("h-5 w-5", colors.icon)} />
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
