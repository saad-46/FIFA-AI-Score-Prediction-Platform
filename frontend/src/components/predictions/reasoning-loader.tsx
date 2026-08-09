"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Terminal, ShieldAlert, Cpu, Activity, BarChart2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const REASONING_STEPS = [
  { label: "Synthesizing 134 predictive feature vectors", detail: "Form matching, rest days, ELO differential, travel index" },
  { label: "Extracting World Cup-era historical coefficients", detail: "Weighting match significance, venue neutralization factor" },
  { label: "Running XGBoost regressor score estimations", detail: "Home/Away goal projection curves" },
  { label: "Solving double Poisson distribution matrices", detail: "Clustering individual scoreline probabilities" },
  { label: "Executing 100,000 Monte Carlo match simulations", detail: "Reaching statistical convergence on outcome probabilities" },
  { label: "Generating SHAP explanation attributions", detail: "Calculating game-by-game feature contribution values" },
  { label: "Calibrating confidence rating algorithms", detail: "Computing final probability delta and certainty index" },
];

export function ReasoningLoader() {
  const [currentStep, setCurrentStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);

  useEffect(() => {
    const timer = setInterval(() => {
      setCompletedSteps((prev) => [...prev, currentStep]);
      setCurrentStep((prev) => {
        if (prev < REASONING_STEPS.length - 1) {
          return prev + 1;
        } else {
          clearInterval(timer);
          return prev;
        }
      });
    }, 900); // Progress every 900ms to cycle through steps in ~6-7 seconds

    return () => clearInterval(timer);
  }, [currentStep]);

  return (
    <Card className="border border-zinc-800 bg-black/60 shadow-2xl backdrop-blur-md overflow-hidden min-h-[400px] flex flex-col justify-center">
      <CardContent className="p-6 md:p-10 space-y-6">
        {/* Terminal Header */}
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex gap-1.5">
              <span className="w-3 h-3 rounded-full bg-rose-500/80" />
              <span className="w-3 h-3 rounded-full bg-amber-500/80" />
              <span className="w-3 h-3 rounded-full bg-emerald-500/80" />
            </div>
            <span className="font-mono text-xs text-zinc-500 tracking-wider">FIFA_PREDICTION_ENGINE v1.4</span>
          </div>
          <motion.div
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ repeat: Infinity, duration: 1.5 }}
            className="flex items-center gap-1.5 text-xs font-mono text-cyan-400"
          >
            <Cpu className="h-3.5 w-3.5" />
            SIMULATING
          </motion.div>
        </div>

        {/* Console Log */}
        <div className="space-y-4 font-mono text-sm">
          {REASONING_STEPS.map((step, idx) => {
            const isCompleted = completedSteps.includes(idx);
            const isActive = idx === currentStep;
            const isPending = idx > currentStep;

            return (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: isPending ? 0.25 : 1, x: 0 }}
                transition={{ duration: 0.3 }}
                className={`flex gap-3 items-start ${isActive ? "text-cyan-400" : isCompleted ? "text-zinc-400" : "text-zinc-600"}`}
              >
                <div className="mt-1 flex shrink-0 items-center justify-center">
                  {isCompleted ? (
                    <span className="text-cyan-500 text-xs">✓</span>
                  ) : isActive ? (
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping" />
                  ) : (
                    <span className="text-zinc-700 text-xs">·</span>
                  )}
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{step.label}</span>
                    {isActive && (
                      <motion.span
                        animate={{ opacity: [0, 1, 0] }}
                        transition={{ repeat: Infinity, duration: 0.8 }}
                        className="inline-block w-2 h-4 bg-cyan-400"
                      />
                    )}
                  </div>
                  {isActive && (
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 0.8 }}
                      className="text-xs text-zinc-500 italic"
                    >
                      &gt; {step.detail}
                    </motion.p>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
