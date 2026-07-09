import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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

export const metadata: Metadata = {
  title: {
    default: "FIFA AI — Score Prediction Platform",
    template: "%s | FIFA AI",
  },
  description:
    "AI-powered FIFA match score predictions using XGBoost machine learning. Predict win probabilities, expected goals, and tournament analytics.",
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
  themeColor: "#020817",
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
        className={`${geistSans.variable} ${geistMono.variable} antialiased min-h-screen`}
      >
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
