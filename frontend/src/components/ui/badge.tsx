import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary/20 text-primary",
        secondary: "border-transparent bg-surface-2 text-foreground",
        destructive: "border-transparent bg-loss/20 text-loss",
        outline: "border-border text-fg-muted",
        win: "border-win/30 bg-win/20 text-win",
        draw: "border-draw/30 bg-draw/20 text-draw",
        loss: "border-loss/30 bg-loss/20 text-loss",
        live: "border-loss/30 bg-loss/20 text-loss animate-pulse",
        synthetic: "border-purple-500/30 bg-purple-500/20 text-purple-400",
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
