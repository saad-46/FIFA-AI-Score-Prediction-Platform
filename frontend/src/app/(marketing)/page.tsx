"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarketingHeader } from "@/components/layout/marketing-header";
import { Footer } from "@/components/layout/footer";

export default function LandingPage() {
  return (
    <div className="relative flex min-h-screen flex-col bg-background overflow-hidden bg-noise">
      {/* Ambient background glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-[-10%] left-[20%] w-[600px] h-[600px] rounded-full bg-cyan-500/10 blur-[120px]" />
        <div className="absolute bottom-[20%] right-[-10%] w-[500px] h-[500px] rounded-full bg-emerald-500/5 blur-[100px]" />
      </div>

      <MarketingHeader />

      <main className="flex-1 flex flex-col justify-center px-6 lg:px-16 max-w-7xl mx-auto w-full py-20 lg:py-32">
        <div className="max-w-4xl space-y-12">
          {/* Subtle Tagline */}
          <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6 }}
            className="flex items-center gap-3 text-xs tracking-[0.2em] font-mono text-cyan-400 uppercase"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            FIFA Analytics Lab // World Cup 2026 — Complete
          </motion.div>

          {/* Huge Cinematic Left-Aligned Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
            className="text-6xl sm:text-7xl lg:text-9xl font-extrabold tracking-tight text-foreground leading-[0.85] font-sans uppercase"
          >
            Relive
            <br />
            The
            <br />
            Tournament
            <br />
            <span className="text-zinc-800 dark:text-zinc-700">Understand Every</span>
            <br />
            Prediction<span className="text-cyan-400 animate-pulse">.</span>
          </motion.h1>

          {/* Minimal Copy with perfect rhythm */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.9 }}
            transition={{ delay: 0.4, duration: 0.8 }}
            className="max-w-xl text-lg sm:text-xl font-normal text-fg-muted leading-relaxed font-sans"
          >
            Every match of the 2026 World Cup, scored against a model frozen before a
            ball was kicked. Poisson scorelines, calibrated probabilities and SHAP
            explanations — with the misses shown alongside the hits.
          </motion.p>

          {/* Call to actions - subtle border glows, no generic flashy stuff */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.6 }}
            className="flex flex-wrap items-center gap-6 pt-4"
          >
            <Link href="/predict" className="focus-visible:outline-none">
              <Button size="xl" className="bg-primary hover:bg-primary-hover text-slate-950 font-mono uppercase tracking-wider text-xs px-8 h-12 shadow-lg shadow-cyan-500/10 cursor-pointer">
                Configure Simulation
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
            <Link href="/tournaments" className="focus-visible:outline-none">
              <Button size="xl" variant="outline" className="border-border text-foreground hover:bg-surface-2 font-mono uppercase tracking-wider text-xs px-8 h-12 cursor-pointer">
                Tournament Intelligence
              </Button>
            </Link>
          </motion.div>
        </div>

        {/* Minimal Contextual Facts Footer Row */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7, duration: 1 }}
          className="mt-24 lg:mt-40 grid grid-cols-2 md:grid-cols-4 gap-8 border-t border-border/60 pt-10"
        >
          <div>
            <span className="block text-xs font-mono text-fg-muted uppercase tracking-wider">Computation Models</span>
            <span className="block mt-1 text-lg font-bold font-mono">XGBoost + Poisson</span>
          </div>
          {/* Every figure here is checkable against the canonical dataset or
              the published backtest. The old "134 Vectors" was the legacy
              model's feature count and read as a claim about the current one. */}
          <div>
            <span className="block text-xs font-mono text-fg-muted uppercase tracking-wider">World Cup Matches</span>
            <span className="block mt-1 text-lg font-bold font-mono">1,069 · 1930—2026</span>
          </div>
          <div>
            <span className="block text-xs font-mono text-fg-muted uppercase tracking-wider">Simulation Iterations</span>
            <span className="block mt-1 text-lg font-bold font-mono">Up to 100k Monte Carlo</span>
          </div>
          <div>
            <span className="block text-xs font-mono text-fg-muted uppercase tracking-wider">WC2026 Backtest</span>
            <span className="block mt-1 text-lg font-bold font-mono">70.2% · 73 of 104</span>
          </div>
        </motion.div>
      </main>

      <Footer />
    </div>
  );
}
