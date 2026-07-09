import Link from "next/link";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center px-4">
      <Compass className="h-12 w-12 text-fg-muted/40 mb-4" aria-hidden="true" />
      <h1 className="text-xl font-semibold text-foreground">Off the pitch</h1>
      <p className="text-fg-muted text-sm mt-2 max-w-sm">
        This page doesn&apos;t exist. Let&apos;s get you back on target.
      </p>
      <Button variant="gradient" className="mt-6" asChild>
        <Link href="/">Go home</Link>
      </Button>
    </div>
  );
}
