import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded border px-2 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-primary/25 bg-primary/10 text-primary",
        secondary: "border-transparent bg-surface-2 text-foreground",
        destructive: "border-transparent bg-loss/20 text-loss",
        outline: "border-border text-fg-muted",
        win: "border-win/30 bg-win/10 text-win",
        draw: "border-draw/30 bg-draw/10 text-draw",
        loss: "border-loss/30 bg-loss/10 text-loss",
        live: "border-loss/30 bg-loss/20 text-loss animate-pulse",
        // Marks placeholder data. Amber, the warning token -- it was purple, the one
        // hue the palette rules out.
        synthetic: "border-warning/30 bg-warning/10 text-warning",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
