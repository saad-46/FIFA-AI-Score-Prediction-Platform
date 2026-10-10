import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "FIFA AI — World Cup 2026, played and measured",
  description:
    "Every match of the 2026 World Cup, the squads that played it, a match predictor and a tournament simulator, with the model's picks shown against the real results.",
};

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
