import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "FIFA World Cup 2026 Intelligence Platform",
  description:
    "AI-powered match score predictions, ELO metrics, and Monte Carlo tournament simulations built for football analysts.",
};

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
