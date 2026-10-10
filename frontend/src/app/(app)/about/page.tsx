import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/page-header";
import { SectionHeader } from "@/components/ui/section";

export const metadata: Metadata = {
  title: "About",
  description: "What this site is, how its predictions are made, and where they fall short.",
};

/**
 * About.
 *
 * Plain prose in a reading column. Every statement here is one the product can
 * back: no feature counts or accuracy claims that depend on which prediction
 * engine a deployment happens to run. Figures that are measured live elsewhere
 * (the backtest, the squad totals) are linked to rather than restated.
 */
export default function AboutPage() {
  return (
    <div className="max-w-2xl space-y-10">
      <PageHeader
        title="About"
        description="What this site is, how its predictions are made, and where they fall short."
      />

      <section aria-labelledby="what-heading" className="space-y-3">
        <SectionHeader id="what-heading" title="What this is" />
        <div className="space-y-3 text-sm leading-relaxed text-fg-muted">
          <p>
            A record of the 2026 FIFA World Cup — all 104 matches, the 48 squads, the group tables and the knockout
            bracket — alongside a model that estimates the outcome of international matches.
          </p>
          <p>
            The tournament has been played. Nothing here predicts it in advance: the match predictor answers
            hypothetical fixtures, the simulator shows how likely each team was to go far, and the &ldquo;Model vs
            reality&rdquo; view sets predictions that were fixed beforehand against what actually happened.
          </p>
        </div>
      </section>

      <section aria-labelledby="how-heading" className="space-y-3">
        <SectionHeader id="how-heading" title="How a prediction is made" />
        <ol className="space-y-3 text-sm leading-relaxed text-fg-muted">
          <li>
            <span className="font-semibold text-foreground">Team strength.</span> Each team carries a rating built
            from its past results, updated match by match in date order, so a result never informs the rating used
            to predict it.
          </li>
          <li>
            <span className="font-semibold text-foreground">Expected goals.</span> From the two teams&apos; ratings,
            recent form and the venue, the model estimates how many goals each side is expected to score.
          </li>
          <li>
            <span className="font-semibold text-foreground">Scorelines.</span> Those two rates give a probability for
            every scoreline, and adding them up gives the chance of a win, a draw or a loss.
          </li>
          <li>
            <span className="font-semibold text-foreground">Tournaments.</span> The simulator plays the 48-team format
            thousands of times with those match probabilities and counts how often each team reaches each round.
          </li>
        </ol>
        <p className="text-sm leading-relaxed text-fg-muted">
          Every prediction shows the model version that produced it, and every simulation states which data it used.
        </p>
      </section>

      <section aria-labelledby="limits-heading" className="space-y-3">
        <SectionHeader id="limits-heading" title="Limits" />
        <ul className="space-y-3 text-sm leading-relaxed text-fg-muted">
          <li>
            <span className="font-semibold text-foreground">Results only.</span> The model knows match results. It
            knows nothing about injuries, suspensions, line-ups, tactics or individual players.
          </li>
          <li>
            <span className="font-semibold text-foreground">Probabilities, not forecasts.</span> A 60% favourite loses
            or draws four times in ten. Even the single most likely scoreline usually has well under a one-in-five chance.
          </li>
          <li>
            <span className="font-semibold text-foreground">One tournament is a small sample.</span> The 2026
            evaluation covers 104 matches. It shows how the model did; it cannot show how good the model is.
          </li>
          <li>
            <span className="font-semibold text-foreground">Goal timing is not held.</span> The match record has final
            scores, not the minute of each goal, so no goal-timing analysis is shown.
          </li>
          <li>
            <span className="font-semibold text-foreground">Photographs are partial.</span> Player photographs are
            stored with the site and added team by team. A player without one is shown by his initials; no image is
            loaded from anywhere else.
          </li>
        </ul>
      </section>

      <p className="border-t border-border pt-4 text-xs leading-relaxed text-fg-subtle">
        For entertainment and analysis only. This site is not affiliated with, endorsed by or connected to FIFA.
      </p>
    </div>
  );
}
