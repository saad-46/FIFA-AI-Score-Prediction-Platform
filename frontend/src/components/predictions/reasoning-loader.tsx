"use client";

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Terminal, ShieldAlert, Cpu, Activity, BarChart2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

/**
 * The stages the prediction request actually goes through, in order.
 *
 * Every line here corresponds to real work in the backend pipeline
 * (app/services/prediction_service.py -> the active model adapter). The
 * previous copy claimed things the single-match path never does — most
 * notably "Executing 100,000 Monte Carlo match simulations", which belongs to
 * the *tournament* simulator, not a match prediction — plus a fixed "134
 * feature vectors" and a "travel index" that is not a feature. A loading state
 * that narrates work the product does not perform is the same category of
 * problem as a fabricated statistic, so it is stated accurately instead.
 */
const REASONING_STEPS = [
  { label: "Building the match feature vector", detail: "Elo ratings, recent form, rankings and venue context" },
  { label: "Reading World Cup match history", detail: "Prior meetings and each side's tournament record" },
  { label: "Estimating expected goals", detail: "Gradient-boosted regressors for each side" },
  { label: "Deriving the scoreline distribution", detail: "Poisson over the two expected-goal rates" },
  { label: "Resolving outcome probabilities", detail: "Calibrated win / draw / loss split" },
  { label: "Attributing the prediction", detail: "SHAP contributions for the driving features" },
];

export function ReasoningLoader() {
  const reduceMotion = useReducedMotion();
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
          {/* Progress read-out rather than macOS traffic-light dots: the dots
              were decoration that implied a window chrome this panel does not
              have, and they spent three semantic colours on nothing. */}
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs tracking-wider text-zinc-500">
              PREDICTION PIPELINE
            </span>
            <span className="font-mono text-xs tabular-nums text-zinc-600">
              {Math.min(currentStep + 1, REASONING_STEPS.length)}/{REASONING_STEPS.length}
            </span>
          </div>
          <motion.div
            animate={reduceMotion ? { opacity: 1 } : { opacity: [0.3, 1, 0.3] }}
            transition={reduceMotion ? undefined : { repeat: Infinity, duration: 1.5 }}
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
                initial={reduceMotion ? false : { opacity: 0, x: -10 }}
                animate={{ opacity: isPending ? 0.25 : 1, x: 0 }}
                transition={{ duration: 0.3 }}
                className={`flex gap-3 items-start ${isActive ? "text-cyan-400" : isCompleted ? "text-zinc-400" : "text-zinc-600"}`}
              >
                <div className="mt-1 flex shrink-0 items-center justify-center">
                  {isCompleted ? (
                    <span className="text-cyan-500 text-xs">✓</span>
                  ) : isActive ? (
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 motion-safe:animate-ping" />
                  ) : (
                    <span className="text-zinc-700 text-xs">·</span>
                  )}
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{step.label}</span>
                    {isActive && (
                      <motion.span
                        animate={reduceMotion ? { opacity: 1 } : { opacity: [0, 1, 0] }}
                        transition={reduceMotion ? undefined : { repeat: Infinity, duration: 0.8 }}
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
