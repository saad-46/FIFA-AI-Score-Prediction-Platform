import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Display face for titles, team names and scorelines. Self-hosted by next/font
// at build time: no request to a font CDN is made from the browser.
const barlowCondensed = Barlow_Condensed({
  variable: "--font-barlow-condensed",
  subsets: ["latin", "latin-ext"],
  weight: ["500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "FIFA AI — Score Prediction Platform",
    template: "%s | FIFA AI",
  },
  description:
    "Football match predictions and World Cup 2026 analysis: win probabilities, expected goals, squads, the full bracket and tournament simulations.",
  keywords: [
    "FIFA",
    "football",
    "soccer",
    "AI prediction",
    "score prediction",
    "machine learning",
    "analytics",
  ],
  openGraph: {
    type: "website",
    locale: "en_US",
    title: "FIFA AI — Score Prediction Platform",
    description: "AI-powered FIFA match score predictions",
    siteName: "FIFA AI",
  },
};

export const viewport: Viewport = {
  themeColor: "#070a11",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${barlowCondensed.variable} antialiased min-h-screen`}
      >
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
